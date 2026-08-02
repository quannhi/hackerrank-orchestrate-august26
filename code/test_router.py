from dotenv import load_dotenv
from context_builder import ContextBuilder
from router_llm import LLMRouter

load_dotenv()

cb = ContextBuilder()
router = LLMRouter()

sample_msg_id = cb.messages_df.iloc[0]["message_id"]
context = cb.get_message_context(sample_msg_id)

decision = router.analyze_message(context)

print("--- VERIFIED OUTPUT SCHEMA ---")
for col in ["message_id", "action", "message_type", "reason", "confidence", "evidence_message_ids"]:
    val = decision.get(col, context.get(col, ""))
    print(f"{col}: {val}")
