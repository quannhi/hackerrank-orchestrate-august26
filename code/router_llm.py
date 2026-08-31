import asyncio
import json
import os
from enum import Enum
from google import genai
from google.genai import types
from pydantic import BaseModel, Field


class ActionEnum(str, Enum):
    notify = "notify"
    digest = "digest"
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
        description="The routing action: notify, digest, or mute."
    )
    message_type: MsgTypeEnum = Field(
        description="The specific category of the message."
    )
    reason: str = Field(
        description="A 1-2 sentence explanation referencing evidence IDs explicitly if context exists."
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
        evidence_formatted = context.get("evidence_formatted", "none")

        history_summary = []
        for pm in past_msgs:
            history_summary.append(
                f"- [Evidence ID: {pm.get('message_id')}] Text: '{pm.get('message_text')}' | "
                f"Replied: {pm.get('message_replied')}, Dismissed: {pm.get('notification_dismissed')}"
            )
        history_str = (
            "\n".join(history_summary)
            if history_summary
            else "No prior message history."
        )

        return f"""
        You are an intelligent notification router. Analyze the following incoming message and its context to decide its routing action and category.

        [CRITICAL EVALUATION POLICY - STRICT NOTIFY vs. DIGEST SEPARATION]
        1. DEFAULT TO DIGEST: Assume messages belong in 'digest' unless strict criteria for 'notify' or 'mute' are met.
        2. NOTIFY CRITERIA (Strictly Limited):
        - ONLY use 'notify' for time-critical emergencies, direct personal 1:1 user messages requiring an immediate reply, or active security alerts.
        - DO NOT use 'notify' for marketing, order status, time-limited sales, business updates, or routine calendar reminders—even if they contain words like "urgent", "limited time", or "action required".
        3. UNKNOWN / FIRST-CONTACT RULE:
        - If user history is empty ('none') and sender is a business or unknown party, route to 'digest' by default. Never escalate first-contact standard messages to 'notify'.
        [ROUTING RULES]
        - ACTION 'mute': Use for scam, spam, heavy forwards, or domain_mismatch.
        - ACTION 'notify': Use for urgent matters, personal direct messages, critical events, or requested payment updates.
        - ACTION 'digest': Use for promotions, standard business updates, or low-priority interactions.

        [EVIDENCE REQUIREMENTS]
        Available Evidence IDs for this context: {evidence_formatted}
        If evidence IDs exist (not 'none'), your reason MUST explicitly mention the evidence ID(s) and signal.

        [MESSAGE DETAILS]
        - Message ID: {context.get('message_id')}
        - Text: "{context.get('message_text', '')}"
        - Conversation Type: {context.get('conversation_type')}
        - Forwarded Count: {context.get('forwarded_count')}

        [SECURITY & HISTORY CONTEXT]
        - Domain Mismatch: {flags.get('domain_mismatch')}
        - Business Verified: {flags.get('is_business_verified')}
        - Prior User Reports: {flags.get('has_prior_user_reports')}
        - Prior User Mutes: {flags.get('has_prior_user_mutes')}
        - User Reply Rate: {metrics.get('reply_rate', 0.0):.2f}

        [HISTORICAL MESSAGES]
        {history_str}
        """

    async def _execute_single_call(self, context: dict) -> dict:
        evidence_str = context.get("evidence_formatted", "none")
        media_path = context.get("media_path")
        uploaded_file = None

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
                "action": "digest",
                "message_type": "unknown",
                "reason": f"Fallback applied: Request timed out after {self.request_timeout} seconds.",
                "confidence": 0.50,
                "evidence_message_ids": evidence_str,
            }
        except Exception as e:
            print(f"\n❌ ERROR: Message {msg_id} failed: {e}")
            return {
                "action": "digest",
                "message_type": "unknown",
                "reason": f"Fallback applied due to API error: {str(e)}",
                "confidence": 0.50,
                "evidence_message_ids": evidence_str,
            }