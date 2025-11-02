# Bank Statement Preprocessing Utility

## Overview

The `preprocess_statement.py` utility is a **universal preprocessor** that handles both ZKB and Revolut bank statements, producing fully preprocessed, dashboard-ready CSV files.

## Features

### Universal Processing

- ✅ **Auto-detects** bank type (ZKB or Revolut)
- ✅ Converts both formats to standardized 8-column output
- ✅ Works with raw downloaded statements

### ZKB-Specific Features

- ✅ **Expands multi-line transactions**: Groups like "Debit Mobile Banking (3)" are split into individual transactions
- ✅ **Removes parent summary rows**: Only keeps actual transactions, not the summaries
- ✅ Converts from 12-column to 8-column format
- ✅ Handles Debit CHF, Credit CHF, and Amount details columns

### Revolut-Specific Features

- ✅ Converts from Revolut's format to normalized format
- ✅ Uses Completed Date as transaction date
- ✅ Preserves Type, Fee, and Currency information

### Common Features

- ✅ **Fixes vault amounts**: Transfers TO vault pockets are made negative (money out)
- ✅ **Auto-categorizes**: Uses merchant mapping + keyword matching
- ✅ **Sorts by date**: Newest transactions first
- ✅ **Dashboard-ready**: Output can be directly uploaded to Django dashboard

## Output Format

All statements are converted to this 8-column format:

```
value_date,description,type,amount,currency,fee,reference,Category
```

## Usage

### Basic Usage (Auto-detect)

```bash
cd /Users/darkeraser/Documents/dev/FinanceTracker/faster/helpers

# Process any statement - auto-detects ZKB or Revolut
python3.13 preprocess_statement.py "../../downloads/Account statement.csv"

# Output: preprocessed_Account statement.csv
```

### Force Bank Type

```bash
# Force ZKB processing
python3.13 preprocess_statement.py input.csv --type zkb

# Force Revolut processing
python3.13 preprocess_statement.py input.csv --type revolut
```

### Custom Output File

```bash
python3.13 preprocess_statement.py input.csv -o ../../data/zkb_2025_10.csv
```

### Quiet Mode

```bash
python3.13 preprocess_statement.py input.csv -q
# Only prints the output file path
```

## Example Output

### ZKB Statement

```
================================================================================
Bank Statement Preprocessor
================================================================================
Bank Type: ZKB
Input:     /Users/darkeraser/Downloads/Account statement 20241002160341.csv
Output:    /Users/darkeraser/Downloads/preprocessed_Account statement 20241002160341.csv

Step 1: Reading original statement...
  ✓ Read 987 rows
  ✓ Columns: Date, Booking text, Curr, Amount details, ZKB reference...

Step 2: Expanding ZKB multi-line transactions...
  ✓ Found 103 child transactions
  ✓ Removed 27 parent summary rows
  ✓ Result: 960 individual transactions

Step 3: Converting to normalized format...
  ✓ Converted to 8-column format
  ✓ Columns: value_date, description, type, amount, currency, fee, reference, Category

Step 4: Fixing vault transfer amounts...
  ✓ No vault transfers to fix

Step 5: Categorizing transactions...
  ✓ Loaded 1240 merchant mappings

  Category distribution:
    Rent: 245
    Groceries: 156
    Restaurants: 89
    Transport: 67
    Uncounted: 42
    ...

  ⚠️  42 transactions categorized as 'Uncounted'
  Consider running merchant_classifier.py to categorize them

Step 6: Saving preprocessed file...
  ✓ Saved 960 transactions

================================================================================
✅ Preprocessing complete!
================================================================================

Output file ready to upload to dashboard:
  /Users/darkeraser/Downloads/preprocessed_Account statement 20241002160341.csv

Summary:
  - Child transactions found: 103
  - Parent rows removed: 27
  - Vault transfers fixed: 0
  - Final transactions: 960
  - Date range: 2023-10-03 to 2024-10-02
```

### Revolut Statement

```
================================================================================
Bank Statement Preprocessor
================================================================================
Bank Type: REVOLUT
Input:     /Users/darkeraser/Downloads/Revolut statement_2024-01-01_2025-01-01.csv
Output:    /Users/darkeraser/Downloads/preprocessed_Revolut statement_2024-01-01_2025-01-01.csv

Step 1: Reading original statement...
  ✓ Read 1543 rows
  ✓ Columns: Type, Product, Started Date, Completed Date, Description...

Step 2: Skipping (Revolut has no multi-line transactions)

Step 3: Converting to normalized format...
  ✓ Converted to 8-column format
  ✓ Columns: value_date, description, type, amount, currency, fee, reference, Category

Step 4: Fixing vault transfer amounts...
  ✓ Fixed 23 vault transfers (made negative)

Step 5: Categorizing transactions...
  ✓ Loaded 1240 merchant mappings

  Category distribution:
    Groceries: 312
    Restaurants: 245
    Vault: 89
    Transport: 78
    Uncounted: 156
    ...

Step 6: Saving preprocessed file...
  ✓ Saved 1543 transactions

================================================================================
✅ Preprocessing complete!
================================================================================

Output file ready to upload to dashboard:
  /Users/darkeraser/Downloads/preprocessed_Revolut statement_2024-01-01_2025-01-01.csv

Summary:
  - Vault transfers fixed: 23
  - Final transactions: 1543
  - Date range: 2024-01-01 to 2025-01-01
```

## What Gets Fixed

### ZKB Multi-line Transactions

**Before preprocessing:**

```csv
Date;Booking text;...;Debit CHF
"31.12.2024";"Debit Standing order (2)";...;"3173.0"
"";"Alb H., A. & A., CH-8053 Zürich";...;"3058.0"
"";"Alb H., A. & A., CH-8053 Zürich";...;"115.0"
```

**After preprocessing:**

```csv
value_date,description,type,amount,currency,fee,reference,Category
31.12.2024,"Alb H., A. & A., CH-8053 Zürich",,-3058.0,CHF,0.0,,Rent
31.12.2024,"Alb H., A. & A., CH-8053 Zürich",,-115.0,CHF,0.0,,Rent
```

**Key changes:**

- ✅ Parent summary row ("Debit Standing order (2)") removed
- ✅ Child transactions now have dates filled in
- ✅ Only individual transactions remain
- ✅ Amounts are properly negative (debits)

### Vault Transfer Amounts

**Before preprocessing:**

```csv
value_date,description,type,amount,currency,fee,reference,Category
2024-10-15,To CHF Vault,Transfer,150.0,CHF,0.0,,
2024-10-20,To Pocket Gaming,Transfer,50.0,EUR,0.0,,
```

**After preprocessing:**

```csv
value_date,description,type,amount,currency,fee,reference,Category
2024-10-15,To CHF Vault,Transfer,-150.0,CHF,0.0,,Vault
2024-10-20,To Pocket Gaming,Transfer,-50.0,EUR,0.0,,Vault
```

**Key changes:**

- ✅ Amounts made negative (money leaving main account)
- ✅ Categorized as "Vault"

## Upload to Dashboard

After preprocessing, upload the file to the Django dashboard:

1. Start the Django server:

   ```bash
   cd /Users/darkeraser/Documents/dev/FinanceTracker/faster
   python manage.py runserver
   ```

2. Navigate to: `http://localhost:8000/transactions/dashboard/`

3. Upload the preprocessed CSV file

4. View your categorized transactions and analytics!

## Improving Categorization

If you have many "Uncounted" transactions, you can improve categorization:

1. Run the merchant classifier:

   ```bash
   cd /Users/darkeraser/Documents/dev/FinanceTracker/faster/helpers
   python3.13 merchant_classifier.py
   ```

2. This will prompt you to categorize unknown merchants and save them to `merchant_category_mapping.json`

3. Re-run the preprocessing to apply the new categorizations:
   ```bash
   python3.13 preprocess_statement.py "input.csv"
   ```

## File Locations

- **Universal Preprocessor**: `faster/helpers/preprocess_statement.py` ⭐
- **ZKB-only Preprocessor**: `faster/helpers/preprocess_zkb_statement.py` (legacy)
- **Merchant Mapping**: `faster/helpers/merchant_category_mapping.json`
- **Category Keywords**: `faster/helpers/finance_utils.py`
- **Raw Downloads**: `~/Downloads/` (bank statement files)
- **Processed Files**: `data/` or custom output location

## Bank Statement Formats

### ZKB Input Format (12 columns, semicolon-separated)

```
Date;Booking text;Curr;Amount details;ZKB reference;Reference number;Debit CHF;Credit CHF;Value date;Balance CHF;Payment purpose;Details
```

### Revolut Input Format (11 columns, comma-separated)

```
Type,Product,Started Date,Completed Date,Description,Amount,Fee,Currency,State,Balance,Category
```

### Normalized Output Format (8 columns, comma-separated)

```
value_date,description,type,amount,currency,fee,reference,Category
```

## Troubleshooting

### "Could not detect bank type"

- Use `--type zkb` or `--type revolut` to force the bank type
- Check that your CSV has the expected columns

### "Error reading input file"

- Make sure the file is a valid CSV
- ZKB files should use semicolon (;) separator
- Revolut files should use comma (,) separator

### Amounts are all 0.0

- **ZKB**: Check for "Debit CHF", "Credit CHF", or "Amount details" columns
- **Revolut**: Check for "Amount" column
- Ensure amounts use correct decimal format (123.45 or 123,45)

### Dates are missing

- **ZKB**: Check that "Date" or "Value date" column exists
- **Revolut**: Check for "Completed Date" or "Started Date" column
- Multi-line child transactions with empty dates are normal - they will be filled in

### Parent transactions not removed (ZKB)

- Check that parent transactions end with `(n)` pattern like "(2)" or "(3)"
- Script uses regex pattern `\(\d+\)\s*$` to detect parent rows
