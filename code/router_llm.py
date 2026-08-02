import os
import json
from pydantic import BaseModel, Field
from enum import Enum
from google import genai
from google.genai import types


# ---------------------------------------------------------------------------
# 1. Define Strict Output Schema using Pydantic
# ---------------------------------------------------------------------------
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
        description="A 1-2 sentence explanation of why this decision was made, referencing context flags."
    )
    confidence: str = Field(
        description="High, medium, or low confidence in this classification."
    )


# ---------------------------------------------------------------------------
# 2. Main LLM Router Class
# ---------------------------------------------------------------------------
class LLMRouter:

    def __init__(self):
        # Automatically picks up GEMINI_API_KEY from the environment
        self.client = genai.Client()
        self.model_name = "gemini-3.5-flash-lite"

    def construct_prompt(self, context: dict) -> str:
        """Translates the rich context dictionary into a clear prompt for Gemini."""

        flags = context.get("security_flags", {})
        metrics = context.get("metrics", {})
        past_msgs = context.get("user_sender_history", [])

        # Format past interactions for Gemini to cite if necessary
        history_summary = []
        for pm in past_msgs:
            history_summary.append(
                f"- [ID: {pm.get('message_id')}] Text: '{pm.get('message_text')}' | Replied: {pm.get('message_replied')}, Dismissed: {pm.get('notification_dismissed')}"
            )
        history_str = (
            "\n".join(history_summary)
            if history_summary
            else "No prior message history found."
        )

        prompt = f"""
        You are an intelligent notification router. Analyze the following incoming message and its context to decide its routing action and category.
        
        [ROUTING RULES]
        - ACTION 'mute': Use for spam, scams, heavy forwards, or if domain_mismatch is True.
        - ACTION 'notify': Use for urgent matters, personal direct messages, critical events, or requested payment updates.
        - ACTION 'digest': Use for promotions, standard business updates, greetings, or low-priority interactions.
        
        [MESSAGE DETAILS]
        - Message ID: {context.get('message_id')}
        - Text: "{context.get('message_text', '')}"
        - Conversation Type: {context.get('conversation_type')}
        - Forwarded Count: {context.get('forwarded_count')}
        
        [SECURITY & HISTORY CONTEXT]
        - Domain Mismatch (Scam Risk): {flags.get('domain_mismatch')}
        - Business Verified: {flags.get('is_business_verified')}
        - Prior User Reports: {flags.get('has_prior_user_reports')}
        - Prior User Mutes: {flags.get('has_prior_user_mutes')}
        - User Historical Reply Rate: {metrics.get('reply_rate', 0.0):.2f} (1.0 = always replies, 0.0 = never replies)
        
        [PAST HISTORY MESSAGES WITH SENDER/GROUP]
        {history_str}
        
        Analyze the text, the provided context, and any attached media to classify this message accurately.
        """
        return prompt

    def analyze_message(self, context: dict) -> dict:
        """Sends context and media to Gemini and returns structured decision with evidence IDs."""

        # Prepare default evidence_message_ids string from context builder
        raw_evidence = context.get("evidence_ids", [])
        evidence_str = " ".join(raw_evidence) if isinstance(
            raw_evidence, list) else str(raw_evidence)

        try:
            contents = [self.construct_prompt(context)]

            # Handle Media attachment
            media_path = context.get("media_path")
            uploaded_file = None
            if media_path and os.path.exists(media_path):
                print(f"Uploading media for analysis: {media_path}")
                uploaded_file = self.client.files.upload(file=media_path)
                contents.append(uploaded_file)

            # Call Gemini with Structured Outputs
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=RouterDecision,
                    temperature=0.1,
                ),
            )

            decision = json.loads(response.text)

            # Cleanup uploaded media file
            if uploaded_file:
                self.client.files.delete(name=uploaded_file.name)

            # Attach evidence_message_ids to final output dictionary
            decision["evidence_message_ids"] = evidence_str
            return decision

        except Exception as e:
            print(
                f"LLM Routing failed for message {context.get('message_id')}: {e}"
            )
            # Safe Fallback
            return {
                "action": "digest",
                "message_type": "unknown",
                "reason": f"Fallback applied due to API error: {str(e)}",
                "confidence": "low",
                "evidence_message_ids": evidence_str,
            }
