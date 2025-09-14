import json
import os

import pandas as pd

from src.finance_utils import CATEGORY_KEYWORDS

MAPPING_FILE = "merchant_category_mapping.json"
DATA_FOLDER = "data"
OUTPUT_PREFIX = "categorized_"

# Load mapping
with open(MAPPING_FILE, "r") as f:
    merchant_mapping = json.load(f)


def categorize_row(row, merchant_col):
    merchant = str(row.get(merchant_col, "")).strip()
    merchant_l = merchant.lower()
    # 1. Try CATEGORY_KEYWORDS
    for cat, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in merchant_l:
                return cat
    # 2. Try mapping
    if merchant in merchant_mapping:
        return merchant_mapping[merchant]
    return "Other"


for fname in os.listdir(DATA_FOLDER):
    if not fname.endswith(".csv"):
        continue
    infile = os.path.join(DATA_FOLDER, fname)
    df = pd.read_csv(infile, sep=";" if "zkb" in fname else ",")
    # Find merchant column
    merchant_col = None
    for col in ["Merchant", "Merchant/Use", "Description", "Booking text"]:
        if col in df.columns:
            merchant_col = col
            break
    if not merchant_col:
        print(f"Skipping {fname}: no merchant/description column found.")
        continue
    df["Category"] = df.apply(lambda row: categorize_row(row, merchant_col), axis=1)
    outname = os.path.join(DATA_FOLDER, OUTPUT_PREFIX + fname)
    df.to_csv(outname, index=False, sep=";" if "zkb" in fname else ",")
    print(f"Wrote {outname}")
