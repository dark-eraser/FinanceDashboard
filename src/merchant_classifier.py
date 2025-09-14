import json
import os

import pandas as pd

from src.finance_utils import CATEGORY_KEYWORDS
from src.google_places_helper import get_place_types

MAPPING_FILE = "merchant_category_mapping.json"


def load_merchant_mapping():
    try:
        with open(MAPPING_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_merchant_mapping(mapping):
    with open(MAPPING_FILE, "w") as f:
        json.dump(mapping, f, indent=2)


def prompt_user_for_category(merchant, place_types):
    print(f"\nMerchant: {merchant}")
    print(f"Google Place Types: {place_types}")
    print("Available categories:")
    for i, cat in enumerate(CATEGORY_KEYWORDS.keys()):
        print(f"  {i+1}. {cat}")
    while True:
        choice = input("Select category number (or press Enter to skip): ")
        if not choice:
            return None
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(CATEGORY_KEYWORDS):
                return list(CATEGORY_KEYWORDS.keys())[idx]
        except ValueError:
            pass
        print("Invalid input. Try again.")


def classify_merchants_with_hybrid(csv_file, merchant_col="Merchant"):
    # Use semicolon delimiter for ZKB files, else default
    if "zkb" in os.path.basename(csv_file).lower():
        df = pd.read_csv(csv_file, sep=";")
    else:
        df = pd.read_csv(csv_file)
    mapping = load_merchant_mapping()
    if merchant_col not in df.columns:
        for fallback in ["Description", "Booking text"]:
            if fallback in df.columns:
                merchant_col = fallback
                break
    for merchant in df[merchant_col].dropna().unique():
        merchant_l = str(merchant).lower()
        # 1. Try CATEGORY_KEYWORDS
        found = False
        for cat, keywords in CATEGORY_KEYWORDS.items():
            for kw in keywords:
                if kw in merchant_l:
                    mapping[merchant] = cat
                    found = True
                    break
            if found:
                break
        if found:
            continue
        # 2. Try mapping
        if merchant in mapping:
            continue
        # 3. Prompt for category or API call
        while True:
            print(f"\nMerchant: {merchant}")
            print("Available categories:")
            for i, cat in enumerate(CATEGORY_KEYWORDS.keys()):
                print(f"  {i+1}. {cat}")
            print("  a. Call Google Places API for more info")
            choice = (
                input("Select category number, or 'a' for API, or Enter to skip: ")
                .strip()
                .lower()
            )
            if not choice:
                break
            if choice == "a":
                place_types = get_place_types(merchant)
                print(f"Google Place Types: {place_types}")
                continue  # re-prompt for category after showing API result
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(CATEGORY_KEYWORDS):
                    selected_cat = list(CATEGORY_KEYWORDS.keys())[idx]
                    mapping[merchant] = selected_cat
                    save_merchant_mapping(mapping)
                    break
            except ValueError:
                pass
            print("Invalid input. Try again.")
    print("\nFinal mapping saved to", MAPPING_FILE)


if __name__ == "__main__":
    data_folder = "data"
    for fname in os.listdir(data_folder):
        if fname.endswith(".csv"):
            print(f"\nProcessing {fname}")
            classify_merchants_with_hybrid(os.path.join(data_folder, fname))
