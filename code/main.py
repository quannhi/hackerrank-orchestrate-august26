import os
import pandas as pd
from dotenv import load_dotenv

# Import custom modules
from context_builder import ContextBuilder
from rule_engine import classify_tier1_regex  # <-- FIXED IMPORT
from router_llm import LLMRouter


def main():
    load_dotenv()

    # Path resolution
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dataset_dir = os.path.join(base_dir, "dataset")
    messages_path = os.path.join(dataset_dir, "messages.csv")
    output_path = os.path.join(base_dir, "output.csv")

    print(f"Loading messages from: {messages_path}")
    messages_df = pd.read_csv(messages_path)

    # Initialize components
    context_builder = ContextBuilder(dataset_dir=dataset_dir)
    llm_router = LLMRouter()  # Uses gemini-3.5-flash-lite

    results = []
    total_messages = len(messages_df)
    tier1_count = 0
    tier2_count = 0

    print(f"Starting message processing for {total_messages} messages...\n")

    for idx, row in messages_df.iterrows():
        msg_id = row["message_id"]
        msg_text = row.get("message_text", "")

        # ------------------------------------------------------------------
        # TIER 1: Fast Deterministic Rule Engine
        # ------------------------------------------------------------------
        action, msg_type, reason = classify_tier1_regex(msg_text)

        if action is not None:
            tier1_count += 1
            ctx = context_builder.get_message_context(msg_id)
            evidence_str = " ".join(ctx.get("evidence_ids", []))

            decision = {
                "message_id": msg_id,
                "action": action,
                "message_type": msg_type,
                "reason": reason,
                "confidence": "high",
                "evidence_message_ids": evidence_str,
            }
            print(
                f"[{idx+1}/{total_messages}] {msg_id} -> TIER 1 MATCH ({action} / {msg_type})"
            )

        # ------------------------------------------------------------------
        # TIER 2: Intelligent LLM Engine (Gemini 3.5 Flash-Lite)
        # ------------------------------------------------------------------
        else:
            tier2_count += 1
            ctx = context_builder.get_message_context(msg_id)
            decision_raw = llm_router.analyze_message(ctx)

            decision = {
                "message_id": msg_id,
                "action": decision_raw.get("action", "digest"),
                "message_type": decision_raw.get("message_type", "unknown"),
                "reason": decision_raw.get(
                    "reason", "Analyzed by LLM context router."
                ),
                "confidence": decision_raw.get("confidence", "medium"),
                "evidence_message_ids": decision_raw.get(
                    "evidence_message_ids", ""
                ),
            }
            print(
                f"[{idx+1}/{total_messages}] {msg_id} -> TIER 2 ROUTED ({decision['action']} / {decision['message_type']})"
            )

        results.append(decision)

    # Convert to DataFrame and enforce required column order
    output_df = pd.DataFrame(results)
    required_cols = [
        "message_id",
        "action",
        "message_type",
        "reason",
        "confidence",
        "evidence_message_ids",
    ]
    output_df = output_df[required_cols]

    # Save output CSV
    output_df.to_csv(output_path, index=False)

    print("\n" + "=" * 50)
    print("PROCESSING COMPLETE!")
    print(f"Total Messages Processed: {total_messages}")
    print(
        f"Filtered by Tier 1 (Regex): {tier1_count} ({tier1_count/total_messages:.1%})"
    )
    print(
        f"Processed by Tier 2 (LLM):   {tier2_count} ({tier2_count/total_messages:.1%})"
    )
    print(f"Output saved to: {output_path}")
    print("=" * 50)


if __name__ == "__main__":
    main()
