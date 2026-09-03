from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
import pandas as pd

from rule_engine import classify_tier1_regex
from router_llm import AsyncLLMRouter
from context_builder import ContextBuilder

history_df = pd.read_csv('../dataset/message_history.csv')

app = FastAPI()

# Enable CORS so your local HTML file/JS can talk to FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize engines
context_builder = ContextBuilder()
llm_router = AsyncLLMRouter(request_timeout=30.0)

class MessageInput(BaseModel):
    text: str
    sender_id: str = "DEFAULT_SENDER"

@app.post("/api/analyze")
async def analyze_message(payload: MessageInput):
    try:
        filtered_history_df = history_df[history_df['sender_user_id'] == payload.sender_id]
        # Pass 1: Tier 1 Regex Scanner
        action, msg_type, reason = classify_tier1_regex(payload.text)
        
        if action is not None:
            return {
                "action": action,
                "message_type": msg_type,
                "reason": reason,
                "confidence": 1.0,
                "evidence_message_ids": "none"
            }

        # Pass 2: Synthesize synthetic context for Tier 2 LLM Router
        synthetic_ctx = {
            "message_id": f"MSG_CUSTOM_{uuid.uuid4().hex[:6].upper()}",
            "message_text": payload.text,
            "conversation_type": "direct",
            "forwarded_count": 0,
            "security_flags": {
                "is_business_verified": True,
                "domain_mismatch": False,
                "has_prior_user_reports": False,
                "has_prior_user_mutes": False,
            },
            "metrics": {
                "reply_rate": 0.5,
                "dismissal_rate": 0.0,
                "total_past_messages": len(filtered_history_df),
            },
            # Pass records as dictionaries with keys expected by router_llm.py
            "user_sender_history": filtered_history_df.to_dict(orient="records"),
            "evidence_formatted": ", ".join(filtered_history_df['message_id'].astype(str).tolist()) or "none",
            "evidence_message_ids": filtered_history_df['message_id'].tolist()
        }

        # Pass 3: Tier 2 Gemini Flash Lite Call
        decision = await llm_router.analyze_message_async(synthetic_ctx)
        return decision
    except Exception as e:
        # Prevents CORS bypass on internal errors
        raise HTTPException(status_code=500, detail=str(e))
