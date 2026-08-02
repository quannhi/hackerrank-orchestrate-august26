import os
import pandas as pd
from dotenv import load_dotenv
from rule_engine import classify_tier1_regex

# 1. Dynamically locate the repository root
# __file__ is code/test_rules.py -> parent is code/ -> parent.parent is repo root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 2. Path to dataset folder
DATASET_DIR = os.path.join(BASE_DIR, "dataset")
MESSAGES_PATH = os.path.join(DATASET_DIR, "messages.csv")

# Load env variables from repo root
load_dotenv(os.path.join(BASE_DIR, ".env"))

print(f"Loading dataset from: {MESSAGES_PATH}")

# 3. Read CSV safely using absolute path
df = pd.read_csv(MESSAGES_PATH)

# 4. Run Tier 1 pass
results = []
for idx, row in df.iterrows():
    action, msg_type, reason = classify_tier1_regex(row["message_text"])
    results.append({
        "message_id": row["message_id"],
        "action": action,
        "message_type": msg_type,
        "reason": reason
    })

res_df = pd.DataFrame(results)

matched = res_df[res_df["action"].notna()]
print(f"Total Messages Evaluated: {len(df)}")
print(f"Filtered by Tier 1 Regex: {len(matched)} ({len(matched)/len(df):.1%})")
print("\nBreakdown by Message Type:")
print(matched["message_type"].value_counts())
