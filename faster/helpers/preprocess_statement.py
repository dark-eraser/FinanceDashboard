#!/usr/bin/env python3
"""
Universal Bank Statement Preprocessor

Handles both ZKB and Revolut statements, producing dashboard-ready CSV files.

Features:
- Auto-detects bank statement type (ZKB or Revolut)
- Expands ZKB multi-line transactions
- Converts to normalized 8-column format
- Fixes vault transfer amounts (makes them negative)
- Applies categorization
- Produces dashboard-ready output

Output format: value_date,description,type,amount,currency,fee,reference,Category
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import pandas as pd

# Add parent directory to path to import finance_utils
sys.path.append(str(Path(__file__).parent))
from finance_utils import CATEGORY_KEYWORDS

MERCHANT_MAPPING_FILE = Path(__file__).parent / "merchant_category_mapping.json"


def load_merchant_mapping():
    """Load merchant-to-category mapping from JSON file"""
    try:
        if MERCHANT_MAPPING_FILE.exists():
            with open(MERCHANT_MAPPING_FILE, "r") as f:
                return json.load(f)
    except json.JSONDecodeError:
        print(f"Warning: Could not parse {MERCHANT_MAPPING_FILE}")
    return {}


def detect_bank_type(filepath):
    """
    Detect if the statement is from ZKB or Revolut.

    Returns: 'zkb', 'revolut', or 'unknown'
    """
    filename = Path(filepath).name.lower()

    # Check filename first
    if "zkb" in filename or "zürcher kantonalbank" in filename:
        return "zkb"
    if "revolut" in filename:
        return "revolut"

    # Check file content - read first few lines
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            first_line = f.readline()

            # ZKB uses semicolon and has "Booking text" column
            if ";" in first_line and "Booking text" in first_line:
                return "zkb"

            # Revolut has specific columns
            if "Type,Product,Started Date,Completed Date,Description" in first_line:
                return "revolut"
    except Exception:
        pass

    return "unknown"


def expand_zkb_child_transactions(df):
    """
    Expand ZKB child transactions by inheriting parent's date and remove parent rows.

    ZKB statements have grouped transactions where:
    - Parent row: Has date, Booking text ends with (n) where n is a number, total amount
    - Child rows: Empty/NaN date field, individual merchant names, individual amounts

    This function:
    1. Assigns the parent's date to all child rows
    2. Marks parent rows for removal (they're just summaries)
    3. Returns only the individual child transactions
    """
    if df is None or df.empty or "Date" not in df.columns:
        return df

    expanded_df = df.copy()
    current_date = None
    parent_indices = []  # Track parent transaction rows to remove

    # Pattern to detect parent transactions: ends with (number)
    parent_pattern = re.compile(r"\(\d+\)\s*$")

    for idx in expanded_df.index:
        # Get date value, handling NaN
        date_val = expanded_df.at[idx, "Date"]
        booking_text = (
            str(expanded_df.at[idx, "Booking text"])
            if "Booking text" in expanded_df.columns
            else ""
        )

        if pd.notna(date_val):
            date_str = str(date_val).strip()
            if date_str and date_str != "Date":  # Valid date found
                current_date = date_str

                # Check if this is a parent transaction (ends with "(n)" pattern)
                if parent_pattern.search(booking_text):
                    # This is a parent row - mark it for removal
                    parent_indices.append(idx)
        elif current_date:  # Empty/NaN date - this is a child transaction
            expanded_df.at[idx, "Date"] = current_date

    # Remove parent transaction rows (they're just summaries)
    if parent_indices:
        expanded_df = expanded_df.drop(parent_indices)
        expanded_df = expanded_df.reset_index(drop=True)

    return expanded_df


def convert_zkb_to_normalized(df):
    """
    Convert ZKB original format (12 columns) to normalized format (8 columns).

    Original format columns:
    Date;Booking text;Curr;Amount details;ZKB reference;Reference number;Debit CHF;Credit CHF;Value date;Balance CHF;Payment purpose;Details

    Normalized format columns:
    value_date,description,type,amount,currency,fee,reference,Category
    """
    normalized = pd.DataFrame()

    # Map Date to value_date
    if "Date" in df.columns:
        normalized["value_date"] = df["Date"]
    elif "Value date" in df.columns:
        normalized["value_date"] = df["Value date"]
    else:
        normalized["value_date"] = ""

    # Map Booking text to description
    if "Booking text" in df.columns:
        normalized["description"] = df["Booking text"]
    else:
        normalized["description"] = ""

    # Type is always empty in ZKB
    normalized["type"] = ""

    # Calculate amount from Debit CHF, Credit CHF, or Amount details
    def compute_amount(row):
        def is_valid_amount(val):
            if pd.isna(val):
                return False
            val_str = str(val).strip().lower()
            return val_str and val_str != "" and val_str != "nan"

        try:
            # Try Debit CHF first (negative)
            if "Debit CHF" in df.columns and is_valid_amount(row["Debit CHF"]):
                debit = str(row["Debit CHF"]).strip()
                return -float(debit.replace(",", "."))

            # Try Credit CHF (positive)
            if "Credit CHF" in df.columns and is_valid_amount(row["Credit CHF"]):
                credit = str(row["Credit CHF"]).strip()
                return float(credit.replace(",", "."))

            # Try Amount details (for child transactions - debits so negative)
            if "Amount details" in df.columns and is_valid_amount(
                row["Amount details"]
            ):
                amount_details = str(row["Amount details"]).strip()
                return -float(amount_details.replace(",", "."))

            return 0.0
        except (ValueError, AttributeError):
            return 0.0

    normalized["amount"] = df.apply(compute_amount, axis=1)

    # Map Curr to currency, default empty values to CHF
    if "Curr" in df.columns:
        normalized["currency"] = df["Curr"].replace("", "CHF").fillna("CHF")
    else:
        normalized["currency"] = "CHF"

    # Fee is always 0 in ZKB
    normalized["fee"] = 0.0

    # Map Reference number to reference
    if "Reference number" in df.columns:
        normalized["reference"] = df["Reference number"]
    else:
        normalized["reference"] = ""

    # Category will be filled by categorization logic
    normalized["Category"] = ""

    return normalized


def convert_revolut_to_normalized(df):
    """
    Convert Revolut format to normalized format (8 columns).

    Revolut format columns:
    Type,Product,Started Date,Completed Date,Description,Amount,Fee,Currency,State,Balance,Category

    Normalized format columns:
    value_date,description,type,amount,currency,fee,reference,Category
    """
    normalized = pd.DataFrame()

    # Use Completed Date as value_date (fallback to Started Date)
    if "Completed Date" in df.columns:
        # Convert datetime to just date
        normalized["value_date"] = pd.to_datetime(
            df["Completed Date"], errors="coerce"
        ).dt.strftime("%Y-%m-%d")
    elif "Started Date" in df.columns:
        normalized["value_date"] = pd.to_datetime(
            df["Started Date"], errors="coerce"
        ).dt.strftime("%Y-%m-%d")
    else:
        normalized["value_date"] = ""

    # Map Description
    if "Description" in df.columns:
        normalized["description"] = df["Description"]
    else:
        normalized["description"] = ""

    # Map Type
    if "Type" in df.columns:
        normalized["type"] = df["Type"]
    else:
        normalized["type"] = ""

    # Map Amount (already in correct sign format)
    if "Amount" in df.columns:
        normalized["amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)
    else:
        normalized["amount"] = 0.0

    # Map Currency
    if "Currency" in df.columns:
        normalized["currency"] = df["Currency"]
    else:
        normalized["currency"] = "EUR"

    # Map Fee
    if "Fee" in df.columns:
        normalized["fee"] = pd.to_numeric(df["Fee"], errors="coerce").fillna(0.0)
    else:
        normalized["fee"] = 0.0

    # Reference is empty for Revolut
    normalized["reference"] = ""

    # Category (may already exist, or will be filled by categorization)
    if "Category" in df.columns:
        normalized["Category"] = df["Category"]
    else:
        normalized["Category"] = ""

    return normalized


def fix_vault_amounts(df):
    """
    Fix vault transfer amounts that are incorrectly positive.
    Transfers TO vault pockets should always be negative (money leaving main account).
    """
    vault_keywords = [
        "to pocket",
        "to chf vault",
        "to chf tablet",
        "to chf gaming",
        "to eur",
    ]

    fixed_count = 0
    for idx, row in df.iterrows():
        description = str(row["description"]).lower()
        amount = row["amount"]

        # Check if this is a vault transfer TO a pocket
        is_vault_transfer = any(keyword in description for keyword in vault_keywords)

        # If it's a vault transfer and amount is positive, make it negative
        if is_vault_transfer and amount > 0:
            df.at[idx, "amount"] = -amount
            fixed_count += 1

    return df, fixed_count


def categorize_transaction(description, merchant_mapping):
    """
    Categorize a transaction based on its description.

    Priority order:
    1. Check merchant mapping (exact match)
    2. Check CATEGORY_KEYWORDS (substring match, longest keyword first for specificity)
    3. Default to "Uncounted"
    """
    if not description or pd.isna(description):
        return "Uncounted"

    desc_str = str(description).strip()
    desc_lower = desc_str.lower()

    # 1. Check merchant mapping (exact match)
    if desc_str in merchant_mapping:
        return merchant_mapping[desc_str]

    # 2. Check CATEGORY_KEYWORDS (substring match, check longest keywords first)
    # Build a list of all (category, keyword) tuples and sort by keyword length (descending)
    all_keywords = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            all_keywords.append((category, keyword))

    # Sort by keyword length (longest first) to prioritize more specific matches
    all_keywords.sort(key=lambda x: len(x[1]), reverse=True)

    for category, keyword in all_keywords:
        if keyword in desc_lower:
            return category

    # 3. Default
    return "Uncounted"


def apply_categorization(df, merchant_mapping):
    """Apply categorization to all transactions"""
    # Only categorize if Category is empty or doesn't exist
    if "Category" not in df.columns:
        df["Category"] = ""

    # Categorize transactions with empty Category
    mask = (df["Category"].fillna("") == "") | (df["Category"] == "Uncounted")
    df.loc[mask, "Category"] = df.loc[mask, "description"].apply(
        lambda desc: categorize_transaction(desc, merchant_mapping)
    )

    return df


def preprocess_statement(input_file, output_file=None, bank_type=None, verbose=True):
    """
    Main preprocessing function for both ZKB and Revolut statements.

    Args:
        input_file: Path to original statement CSV
        output_file: Path for output file (optional, will auto-generate if not provided)
        bank_type: Force bank type ('zkb' or 'revolut', auto-detect if None)
        verbose: Print progress messages

    Returns:
        Path to output file
    """
    input_path = Path(input_file)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    # Detect bank type if not specified
    if bank_type is None:
        bank_type = detect_bank_type(input_file)
        if bank_type == "unknown":
            raise ValueError(
                "Could not detect bank type. Please specify with --type parameter"
            )

    # Generate output filename if not provided
    if output_file is None:
        output_file = input_path.parent / f"preprocessed_{input_path.stem}.csv"

    output_path = Path(output_file)

    if verbose:
        print(f"{'='*80}")
        print(f"Bank Statement Preprocessor")
        print(f"{'='*80}")
        print(f"Bank Type: {bank_type.upper()}")
        print(f"Input:     {input_path}")
        print(f"Output:    {output_path}")
        print()

    # Step 1: Read original file
    if verbose:
        print("Step 1: Reading original statement...")

    try:
        if bank_type == "zkb":
            df = pd.read_csv(input_path, sep=";", dtype=str, encoding="utf-8")
        else:  # revolut
            df = pd.read_csv(input_path, dtype=str, encoding="utf-8")

        df.columns = [col.strip() for col in df.columns]

        if verbose:
            print(f"  ✓ Read {len(df)} rows")
            print(f"  ✓ Columns: {', '.join(df.columns[:5])}...")
    except Exception as e:
        raise ValueError(f"Error reading input file: {e}")

    # Step 2: ZKB-specific - Expand child transactions
    parent_removed = 0
    child_count = 0

    if bank_type == "zkb":
        if verbose:
            print("\nStep 2: Expanding ZKB multi-line transactions...")

        original_row_count = len(df)
        child_count = df["Date"].isna().sum() if "Date" in df.columns else 0
        df = expand_zkb_child_transactions(df)
        parent_removed = original_row_count - len(df)

        if verbose:
            print(f"  ✓ Found {child_count} child transactions")
            print(f"  ✓ Removed {parent_removed} parent summary rows")
            print(f"  ✓ Result: {len(df)} individual transactions")
    else:
        if verbose:
            print("\nStep 2: Skipping (Revolut has no multi-line transactions)")

    # Step 3: Convert to normalized format
    if verbose:
        print("\nStep 3: Converting to normalized format...")

    if bank_type == "zkb":
        df_normalized = convert_zkb_to_normalized(df)
    else:  # revolut
        df_normalized = convert_revolut_to_normalized(df)

    if verbose:
        print(f"  ✓ Converted to 8-column format")
        print(f"  ✓ Columns: {', '.join(df_normalized.columns)}")

    # Step 4: Fix vault amounts
    if verbose:
        print("\nStep 4: Fixing vault transfer amounts...")

    df_fixed, vault_fixed = fix_vault_amounts(df_normalized)

    if verbose:
        if vault_fixed > 0:
            print(f"  ✓ Fixed {vault_fixed} vault transfers (made negative)")
        else:
            print(f"  ✓ No vault transfers to fix")

    # Step 5: Categorization
    if verbose:
        print("\nStep 5: Categorizing transactions...")

    merchant_mapping = load_merchant_mapping()
    if verbose:
        print(f"  ✓ Loaded {len(merchant_mapping)} merchant mappings")

    df_categorized = apply_categorization(df_fixed, merchant_mapping)

    # Print category distribution
    category_counts = df_categorized["Category"].value_counts()
    if verbose:
        print("\n  Category distribution:")
        for cat, count in category_counts.head(10).items():
            print(f"    {cat}: {count}")
        if len(category_counts) > 10:
            print(f"    ... and {len(category_counts) - 10} more categories")

    uncounted = len(df_categorized[df_categorized["Category"] == "Uncounted"])
    if verbose and uncounted > 0:
        print(f"\n  ⚠️  {uncounted} transactions categorized as 'Uncounted'")
        print("  Consider running merchant_classifier.py to categorize them")

    # Step 6: Save to output file
    if verbose:
        print(f"\nStep 6: Saving preprocessed file...")

    # Sort by date (newest first)
    df_categorized["date_sort"] = pd.to_datetime(
        df_categorized["value_date"], format="mixed", dayfirst=True, errors="coerce"
    )
    df_categorized = df_categorized.sort_values("date_sort", ascending=False)
    df_categorized = df_categorized.drop(columns=["date_sort"])

    # Save
    df_categorized.to_csv(output_path, index=False)

    if verbose:
        print(f"  ✓ Saved {len(df_categorized)} transactions")
        print()
        print(f"{'='*80}")
        print(f"✅ Preprocessing complete!")
        print(f"{'='*80}")
        print(f"\nOutput file ready to upload to dashboard:")
        print(f"  {output_path}")
        print()
        print("Summary:")
        if bank_type == "zkb":
            print(f"  - Child transactions found: {child_count}")
            print(f"  - Parent rows removed: {parent_removed}")
        print(f"  - Vault transfers fixed: {vault_fixed}")
        print(f"  - Final transactions: {len(df_categorized)}")

        # Calculate date range safely
        try:
            valid_dates = df_categorized["value_date"].dropna()
            valid_dates = valid_dates[valid_dates != ""]
            if len(valid_dates) > 0:
                # Convert to datetime for proper min/max
                date_series = pd.to_datetime(valid_dates, errors="coerce").dropna()
                if len(date_series) > 0:
                    min_date = date_series.min().strftime("%Y-%m-%d")
                    max_date = date_series.max().strftime("%Y-%m-%d")
                    print(f"  - Date range: {min_date} to {max_date}")
        except Exception:
            pass  # Skip date range if there's any issue

    return output_path


def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(
        description="Preprocess bank statements (ZKB or Revolut) for Django dashboard upload",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-detect bank type and process
  python preprocess_statement.py "Account statement.csv"

  # Force bank type
  python preprocess_statement.py input.csv --type zkb
  python preprocess_statement.py input.csv --type revolut

  # Specify output file
  python preprocess_statement.py input.csv -o output.csv

  # Quiet mode
  python preprocess_statement.py input.csv -q
        """,
    )

    parser.add_argument("input_file", help="Path to original bank statement CSV file")
    parser.add_argument(
        "-o",
        "--output",
        help="Output file path (default: preprocessed_<input_filename>.csv)",
    )
    parser.add_argument(
        "-t",
        "--type",
        choices=["zkb", "revolut"],
        help="Force bank type (auto-detect if not specified)",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Quiet mode (minimal output)"
    )

    args = parser.parse_args()

    try:
        output_file = preprocess_statement(
            args.input_file, args.output, args.type, verbose=not args.quiet
        )

        if args.quiet:
            print(output_file)

        sys.exit(0)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
