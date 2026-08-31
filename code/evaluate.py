import os
import pandas as pd


def evaluate_pipeline_output(csv_path: str = "output.csv"):
    """
    Evaluates generated output.csv for syntax correctness, bounds, and formatting[cite: 1].
    Prints categorized error summaries.
    """
    if not os.path.exists(csv_path):
        print(f"❌ Error: {csv_path} does not exist.")
        return

    df = pd.read_csv(csv_path)
    total_rows = len(df)
    print(f"=== EVALUATING BATCH OUTPUT: {csv_path} ({total_rows} rows) ===\n")

    required_columns = [
        "message_id",
        "action",
        "message_type",
        "reason",
        "confidence",
        "evidence_message_ids",
    ]
    errors = {
        "missing_columns": 0,
        "space_delimiter_bug": 0,
        "empty_evidence_bug": 0,
        "confidence_out_of_bounds": 0,
        "uncited_reason_warning": 0,
    }

    # 1. Column Structure Check
    for col in required_columns:
        if col not in df.columns:
            print(f"❌ Critical: Required column '{col}' is missing.")
            errors["missing_columns"] += 1

    if errors["missing_columns"] > 0:
        return

    # 2. Row Level Audits
    for idx, row in df.iterrows():
        msg_id = row["message_id"]
        ev = str(row["evidence_message_ids"])
        reason = str(row["reason"])

        # Check: Space Separation Bug
        if " " in ev and ";" not in ev and ev != "none":
            print(
                f"❌ Row {idx} ({msg_id}): Space-delimited evidence detected -> '{ev}'"
            )
            errors["space_delimiter_bug"] += 1

        # Check: Empty String Bug
        if pd.isna(row["evidence_message_ids"]) or ev.strip() in ["", "nan"]:
            print(
                f"❌ Row {idx} ({msg_id}): Empty evidence field (must be 'none')"
            )
            errors["empty_evidence_bug"] += 1

        # Check: Numeric Bounds for Confidence
        try:
            conf = float(row["confidence"])
            if conf < 0.0 or conf > 1.0:
                print(
                    f"❌ Row {idx} ({msg_id}): Confidence {conf} out of bounds [0.0, 1.0]"
                )
                errors["confidence_out_of_bounds"] += 1
        except (ValueError, TypeError):
            print(
                f"❌ Row {idx} ({msg_id}): Non-numeric confidence -> '{row['confidence']}'"
            )
            errors["confidence_out_of_bounds"] += 1

        # Check: Grounded Reason (Warn if evidence present but not mentioned in reason)
        if ev != "none":
            first_ev_id = ev.split(";")[0]
            if first_ev_id not in reason:
                errors["uncited_reason_warning"] += 1

    # 3. Summary Printing
    total_errors = sum(errors.values())
    print("\n" + "=" * 50)
    print("EVALUATION SUMMARY")
    print("=" * 50)
    print(f"Total Rows Audited:           {total_rows}")
    print(f"Space Delimiter Errors:        {errors['space_delimiter_bug']}")
    print(f"Empty Evidence String Errors:  {errors['empty_evidence_bug']}")
    print(
        f"Confidence Out-Of-Bounds:      {errors['confidence_out_of_bounds']}"
    )
    print(f"Uncited Evidence Warnings:     {errors['uncited_reason_warning']}")
    print("-" * 50)

    if (
        total_errors - errors["uncited_reason_warning"] == 0
    ):  # Ignore soft warnings for pass flag
        print("✅ PASS: CSV passed all strict evaluation checks!")
    else:
        print(
            f"❌ FAIL: Found {total_errors} issue(s) needing fix before submission."
        )


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_csv = os.path.join(base_dir, "output.csv")
    evaluate_pipeline_output(output_csv)