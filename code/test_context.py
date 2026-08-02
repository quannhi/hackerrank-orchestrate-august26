import json
import os
from context_builder import ContextBuilder

cb = ContextBuilder()

# Select a few representative message IDs to test (e.g. business message, group message, personal message)
sample_ids = [
    cb.messages_df.iloc[0]["message_id"],  # Business message
    cb.messages_df.iloc[3]["message_id"],  # Group message
    cb.messages_df.iloc[1]["message_id"],  # Personal message
]

for msg_id in sample_ids:
    ctx = cb.get_message_context(msg_id)

    print("=" * 60)
    print(f"MESSAGE ID: {ctx['message_id']} ({ctx['conversation_type']})")
    print(f"Text Preview: {repr(ctx['message_text'][:80])}")
    print(f"Media Path: {ctx['media_path']}")

    print("\n--- SECURITY FLAGS ---")
    for flag, val in ctx['security_flags'].items():
        print(f"  {flag}: {val}")

    print("\n--- HISTORICAL METRICS ---")
    for metric, val in ctx['metrics'].items():
        print(f"  {metric}: {val}")

    print(f"\nEvidence Message IDs: {ctx['evidence_ids']}")
    print(f"Past Messages in Context: {len(ctx['user_sender_history'])}")
    print("=" * 60 + "\n")
