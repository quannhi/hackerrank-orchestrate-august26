import os
import time
import pandas as pd
import asyncio
from dotenv import load_dotenv

from context_builder import ContextBuilder
from rule_engine import classify_tier1_regex
from router_llm import AsyncLLMRouter

REQUIRED_INPUT_COLS = ["message_id"]

def validate_input_dataframe(df: pd.DataFrame):
    """Validates required input columns before batch processing."""
    missing = [c for c in REQUIRED_INPUT_COLS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Input dataset is missing required columns: {missing}"
        )

async def process_tier2_batch(
    tier2_items,
    context_builder,
    llm_router,
    concurrency_limit=2,
    delay_between_requests=15.0,
):
    """Processes Tier 2 messages with explicit rate-limit spacing."""
    semaphore = asyncio.Semaphore(concurrency_limit)

    async def process_single(item):
        async with semaphore:
            idx, msg_id = item["idx"], item["message_id"]
            ctx = context_builder.get_message_context(msg_id)

            decision_raw = await llm_router.analyze_message_async(ctx)

            conf = float(decision_raw.get("confidence", 0.8))
            conf_clamped = max(0.0, min(1.0, conf))

            decision = {
                "idx": idx,
                "message_id": msg_id,
                "action": decision_raw.get("action", "digest"),
                "message_type": decision_raw.get("message_type", "unknown"),
                "reason": decision_raw.get(
                    "reason", "Analyzed by LLM context router."
                ),
                "confidence": conf_clamped,
                "evidence_message_ids": decision_raw.get(
                    "evidence_message_ids", "none"
                ),
            }
            print(
                f"[{idx+1}] {msg_id} -> TIER 2 ROUTED ({decision['action']} / {decision['message_type']})"
            )

            # Mandatory sleep per worker slot to respect RPM quota
            await asyncio.sleep(delay_between_requests)
            return decision

    tasks = [process_single(item) for item in tier2_items]
    return await asyncio.gather(*tasks)

async def async_main():
    load_dotenv()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dataset_dir = os.path.join(base_dir, "dataset")
    messages_path = os.path.join(dataset_dir, "messages.csv")
    output_path = os.path.join(base_dir, "output.csv")

    print(f"Loading messages from: {messages_path}")
    messages_df = pd.read_csv(messages_path)
    validate_input_dataframe(messages_df)

    context_builder = ContextBuilder(dataset_dir=dataset_dir)
    # Set timeout explicitly to 30.0 seconds
    llm_router = AsyncLLMRouter(request_timeout=30.0)

    results = []
    tier2_queue = []
    total_messages = len(messages_df)
    tier1_count = 0

    print(f"Starting message processing for {total_messages} messages...\n")

    # Pass 1: Handle Tier 1 Regex Rules locally
    for idx, row in messages_df.iterrows():
        msg_id = row["message_id"]
        msg_text = row.get("message_text", "")
        action, msg_type, reason = classify_tier1_regex(msg_text)

        if action is not None:
            tier1_count += 1
            ctx = context_builder.get_message_context(msg_id)
            evidence_str = ctx.get("evidence_formatted", "none")

            if evidence_str != "none" and evidence_str not in reason:
                reason = f"{reason} (Citing historical context: {evidence_str})"

            results.append({
                "idx": idx,
                "message_id": msg_id,
                "action": action,
                "message_type": msg_type,
                "reason": reason,
                "confidence": 1.0,
                "evidence_message_ids": evidence_str,
            })
            print(f"[{idx+1}/{total_messages}] {msg_id} -> TIER 1 MATCH ({action} / {msg_type})")
        else:
            tier2_queue.append({"idx": idx, "message_id": msg_id})

    # Pass 2: Handle Tier 2 LLM Routing concurrently
    tier2_count = len(tier2_queue)
    if tier2_queue:
        print(f"\nProcessing {tier2_count} Tier 2 messages concurrently...")
        tier2_results = await process_tier2_batch(tier2_queue, context_builder, llm_router, concurrency_limit=3)
        results.extend(tier2_results)

    # Sort results by original message index to maintain dataset order
    results.sort(key=lambda x: x["idx"])
    for r in results:
        del r["idx"]

    # Export to CSV
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
    output_df.to_csv(output_path, index=False)

    print("\n" + "=" * 50)
    print("PROCESSING COMPLETE!")
    print(f"Total Messages Processed: {total_messages}")
    print(f"Filtered by Tier 1 (Regex): {tier1_count} ({tier1_count/total_messages:.1%})")
    print(f"Processed by Tier 2 (LLM):   {tier2_count} ({tier2_count/total_messages:.1%})")
    print(f"Output saved to: {output_path}")
    print("=" * 50)
    # Auto-trigger evaluation audit
    from evaluate import evaluate_pipeline_output

    print("\nRunning automated evaluation checks...")
    evaluate_pipeline_output(output_path)

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()