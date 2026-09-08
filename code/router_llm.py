import asyncio
import json
import os
from enum import Enum
from google import genai
from google.genai import types
from pydantic import BaseModel, Field


class ActionEnum(str, Enum):
    notify = "notify"
    received = "received"
    mute = "mute"


class MsgTypeEnum(str, Enum):
    personal = "personal"
    urgent = "urgent"
    event = "event"
    payment = "payment"
    business_update = "business_update"
    promotion = "promotion"
    greeting = "greeting"
    forward = "forward"
    spam = "spam"
    scam = "scam"
    unknown = "unknown"


class RouterDecision(BaseModel):
    action: ActionEnum = Field(
        description="The routing action: notify, received, or mute."
    )
    message_type: MsgTypeEnum = Field(
        description="The specific category of the message."
    )
    reason: str = Field(
        description="A 1-2 receivedence explanation referencing evidence IDs explicitly if context exists."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score bounded strictly between 0.0 and 1.0.",
    )


class AsyncLLMRouter:

    def __init__(
        self,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        request_timeout: float = 30.0,  # Updated to 30s
    ):
        self.client = genai.Client()
        self.model_name = "gemini-3.5-flash-lite"
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.request_timeout = request_timeout

    def construct_prompt(self, context: dict) -> str:
        flags = context.get("security_flags", {})
        metrics = context.get("metrics", {})
        past_msgs = context.get("user_sender_history", [])
        past_events = context.get('user_sender_events', [])
        evidence_message_ids = context.get("evidence_message_ids", "none")
        evidence_text_formatted = context.get('evidence_formatted', 'none')

        has_prior_user_mutes = False
        has_prior_user_reports = False

        history_summary = []
        conv_type = []
        for pm in past_msgs:
            if pm.get('conversation_type') not in conv_type:
                conv_type.append(pm.get('conversation_type'))
            relevant_row = past_events.loc[past_events['message_id'] == pm.get('message_id')].to_dict(orient = 'records')
            message_events = relevant_row[0] # because orient records returns a list
            if message_events.get('muted_after_message') == 1:
                has_prior_user_mutes = True
            if message_events.get('message_reported') == 1:
                has_prior_user_reports = True
            history_summary.append(
                f"- [Evidence ID: {pm.get('message_id')}] Text: '{pm.get('message_text')}' Type: '{pm.get('conversation_type')}' | "
                f"Replied: {message_events.get('message_replied') == 1}, Dismissed: {message_events.get('notification_dismissed') == 1}, Reaction Time Minutes: {message_events.get('reaction_time_minutes', 'did not reply')}, Muted after receiving: {message_events.get('muted_after_message') == 1}, Reported: {message_events.get('message_reported') == 1} "
            )
        
        history_str = (
            "\n".join(history_summary)
            if history_summary
            else "No prior message history."
        )
        print(history_str)
        return f"""
        You are an intelligent notification router. Analyze the incoming message and its context to determine both the routing action ("notify", "received", "mute") and the category ("personal", "business", "security", "promotional").

        [PRIORITY EVALUATION HIERARCHY]
        Evaluate rules strictly in this order (1 -> 2 -> 3):

        1. RULE 1: MUTE (Highest Priority)
        - MUST ROUTE to 'mute' if ANY of the following apply:
            * Content contains scams, spam, threats, or insults.
            * 'Domain Mismatch' is True.
            * Historical context shows prior user reports/mutes for this specific sender or topic/category/format.
            * High forward count (>3) paired with unverified business/unknown senders.

        2. RULE 2: NOTIFY (Strictly Limited)
        - Route to 'notify' ONLY if the message meets critical real-time thresholds:
            * Immediate physical, financial, or social well-being threat/emergency.
            * Direct 1:1 personal message requiring immediate active human coordination.
            * Critical, real-time security alerts (e.g., 2FA codes, unauthorized login attempts).
        - EXCLUSIONS: Never use 'notify' for routine payment receipts, order statuses, marketing, calendar items, or promotional urgency tricks ("act fast", "limited time").

        3. RULE 3: received (Default Action)
        - Route to 'received' for ALL other standard communications:
            * Cold-start / first-contact messages from unknown parties or businesses.
            * General inquiries, routine business updates, order tracking, and non-urgent personal chatter.

        [EVIDENCE CITATION REQUIREMENT]
        Available Evidence IDs: {evidence_message_ids}
        - If Evidence IDs are prereceived (not 'none'), your generated reason MUST explicitly reference the specific evidence ID(s) and signal (e.g., "Matched evidence ID message_0017 showing past dismissal").

        [INPUT CONTEXT]
        - Message ID: {context.get('message_id')}
        - Text: "{context.get('message_text', '')}"
        - Conversation Type: {', '.join(conv_type)}
        - Forwarded Count: {context.get('forwarded_count')}
        - Security Flags: Domain Mismatch={flags.get('domain_mismatch')}, Verified Business={flags.get('is_business_verified')}
        - Sender History Signals: Prior Reports={has_prior_user_reports}, Prior Mutes={has_prior_user_mutes}, Reply Rate={metrics.get('reply_rate', 0.0):.2f}

        [HISTORICAL MESSAGES]
        {history_str}
        """

    async def _execute_single_call(self, context: dict) -> dict:
        evidence_str = context.get("evidence_message_ids", "none")
        media_path = context.get("media_path")
        uploaded_file = None
        print(evidence_str)
        try:
            if media_path and os.path.exists(media_path):
                uploaded_file = await asyncio.to_thread(
                    self.client.files.upload, file=media_path
                )

            prompt_text = self.construct_prompt(context)
            contents = (
                [uploaded_file, prompt_text] if uploaded_file else [prompt_text]
            )

            chat = self.client.chats.create(
                model=self.model_name,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=RouterDecision,
                    temperature=0.1,
                ),
            )

            for attempt in range(1, self.max_retries + 1):
                try:
                    response = await asyncio.to_thread(
                        chat.send_message, contents
                    )
                    decision = json.loads(response.text)

                    conf = float(decision.get("confidence", 0.8))
                    decision["confidence"] = max(0.0, min(1.0, conf))
                    decision["evidence_message_ids"] = evidence_str
                    return decision

                except Exception as api_err:
                    if attempt == self.max_retries:
                        raise api_err
                    wait_time = self.retry_delay * (2 ** (attempt - 1))
                    await asyncio.sleep(wait_time)

        finally:
            if uploaded_file:
                try:
                    await asyncio.to_thread(
                        self.client.files.delete, name=uploaded_file.name
                    )
                except Exception:
                    pass

    async def analyze_message_async(self, context: dict) -> dict:
        evidence_str = context.get("evidence_formatted", "none")
        msg_id = context.get("message_id")

        try:
            return await asyncio.wait_for(
                self._execute_single_call(context),
                timeout=self.request_timeout,
            )
        except asyncio.TimeoutError:
            print(
                f"\n⚠️ TIMEOUT: Message {msg_id} exceeded {self.request_timeout}s limit. Applying fallback..."
            )
            return {
                "action": "received",
                "message_type": "unknown",
                "reason": f"Fallback applied: Request timed out after {self.request_timeout} seconds.",
                "confidence": 0.50,
                "evidence_message_ids": evidence_str,
            }
        except Exception as e:
            print(f"\n❌ ERROR: Message {msg_id} failed: {e}")
            return {
                "action": "received",
                "message_type": "unknown",
                "reason": f"Fallback applied due to API error: {str(e)}",
                "confidence": 0.50,
                "evidence_message_ids": evidence_str,
            }