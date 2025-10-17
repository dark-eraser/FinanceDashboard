#!/usr/bin/env python3
"""
Normalize various bank statement CSV exports into a single, consistent CSV format for the dashboard.

Outputs CSVs to an output directory preserving source file names with a "normalized_" prefix.

Usage:
    python3 scripts/normalize_statements.py --input-dir original --output-dir normalized --preview 5

The unified output columns are:
    value_date,description,type,amount,currency,fee,reference

Notes:
 - Supports Revolut (comma separated) and ZKB (semicolon separated) samples found in the repository.
 - Tries to be robust to missing fields.
"""
import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Any, Dict

import pandas as pd
from dateutil import parser as dateparser

# Unified column order (source_file and booking_date removed)
OUT_COLS = [
    "value_date",
    "description",
    "type",
    "amount",
    "currency",
    "fee",
    "reference",
]

# ignore absurdly large numbers when scanning free-form fields (likely balances/postal codes)
MAX_SCAN_AMOUNT = 10000.0


def parse_revolut(df: pd.DataFrame) -> pd.DataFrame:
    # Revolut sample uses columns like:
    # Type,Product,Started Date,Completed Date,Description,Amount,Fee,Currency,State,Balance
    out = pd.DataFrame()

    # value_date: prefer Completed Date -> Started Date
    def pick_value_date(row):
        cd = row.get("Completed Date")
        sd = row.get("Started Date")
        chosen = cd if pd.notna(cd) and str(cd).strip() != "" else sd
        return _parse_date(chosen)

    out["value_date"] = df.apply(pick_value_date, axis=1)
    out["description"] = df.get("Description")
    out["type"] = df.get("Type")
    # Amount is signed already in Revolut
    out["amount"] = df.get("Amount").apply(_to_float)
    out["currency"] = df.get("Currency")
    out["fee"] = df.get("Fee").apply(_to_float) if "Fee" in df else None
    out["reference"] = (
        df.get("Description")
        .astype(str)
        .apply(lambda s: _extract_reference_from_desc(s))
    )
    return out


def parse_zkb(df: pd.DataFrame) -> pd.DataFrame:
    """Parse ZKB semicolon CSV into the canonical output schema.

    Strategy:
    - Expand Mobile Banking summary rows with `expand_mobile_summaries_in_df` so children inherit the parent's Date
    - Prefer explicit Debit CHF / Credit CHF columns for amount and sign
    - Fallback to _find_amount_in_record which skips date-like fields
    """
    if df is None or df.empty:
        return pd.DataFrame(columns=OUT_COLS)

    # expand mobile summaries (if present)
    try:
        if "Date" in df.columns:
            df2 = expand_mobile_summaries_in_df(df)
        else:
            df2 = df.copy()
    except Exception:
        df2 = df.copy()

    out = pd.DataFrame()
    # value_date: prefer Value date -> Date
    if "Value date" in df2.columns:
        out["value_date"] = df2["Value date"].apply(
            lambda v: _parse_date(v, dayfirst=True)
        )
    elif "Date" in df2.columns:
        out["value_date"] = df2["Date"].apply(lambda v: _parse_date(v, dayfirst=True))
    else:
        out["value_date"] = None

    # description
    desc_cols = [
        c
        for c in (
            "Booking text",
            "Booking text ",
            "Payment purpose",
            "Payment Purpose",
            "BookingText",
        )
        if c in df2.columns
    ]
    if desc_cols:
        out["description"] = df2[desc_cols[0]].astype(str)
    else:
        # fallback to second column if present
        out["description"] = (
            df2.iloc[:, 1].astype(str)
            if df2.shape[1] > 1
            else df2.iloc[:, 0].astype(str)
        )

    out["type"] = None

    def compute_amount_from_record(rec):
        # rec is a Series
        debit = (
            _to_float(rec.get("Debit CHF"))
            if "Debit CHF" in rec.index or "Debit CHF" in rec
            else None
        )
        credit = (
            _to_float(rec.get("Credit CHF"))
            if "Credit CHF" in rec.index or "Credit CHF" in rec
            else None
        )
        if credit and credit != 0:
            return credit
        if debit and debit != 0:
            return -debit
        # fallback: prioritized field scan
        val, kind = _find_amount_in_record(rec)
        if val is not None:
            if kind == "credit":
                return val
            if kind == "debit":
                return -val
            return val
        return None

    out["amount"] = df2.apply(compute_amount_from_record, axis=1)

    # currency
    if "Curr" in df2.columns:
        out["currency"] = df2["Curr"].fillna("CHF")
    elif "Currency" in df2.columns:
        out["currency"] = df2["Currency"].fillna("CHF")
    else:
        out["currency"] = "CHF"

    out["fee"] = None
    # reference intentionally omitted for ZKB per user request
    out["reference"] = None
    return out


def _parse_date(v, dayfirst=False):
    if pd.isna(v):
        return None
    s = str(v).strip()
    if s == "":
        return None
    try:
        # dateutil parser: use dayfirst for formats like DD.MM.YYYY
        dt = dateparser.parse(s, dayfirst=dayfirst)
        return dt.isoformat()
    except Exception:
        # try replacing dot date
        try:
            if "." in s and len(s.split("."[0])) >= 3:
                parts = [p.zfill(2) for p in s.split(".")]
                return dateparser.parse("-".join(reversed(parts))).isoformat()
        except Exception:
            return s


def _first_numeric_in_record(rec) -> float | None:
    """Return the first value in the record that parses to a float, or None.

    rec may be a dict or pandas Series.
    """
    # prefer explicit debit/credit fields
    if isinstance(rec, dict):
        items = rec.values()
    else:
        items = list(rec.values)
    for v in items:
        try:
            num = _to_float(v)
            if num is not None:
                return num
        except Exception:
            continue
    return None


def _find_amount_in_record(rec) -> tuple[float | None, str | None]:
    """Try to find an amount in the record and return (amount, kind).

    kind is 'debit' or 'credit' or None if unknown.
    Skip any fields that look like 'balance'.
    """
    # preferred explicit columns
    keys = []
    if isinstance(rec, dict):
        keys = list(rec.keys())
    else:
        keys = list(rec.index)

    # candidate priority
    candidates = [
        "Debit CHF",
        "Credit CHF",
        "Debit",
        "Credit",
        "Amount details",
        "Amount",
        "Amt",
    ]
    for k in candidates:
        if k in keys:
            v = rec.get(k)
            num = _to_float(v)
            if num is not None:
                if "debit" in k.lower():
                    return num, "debit"
                if "credit" in k.lower():
                    return num, "credit"
                return num, None

    # fallback: scan all fields except balance-like
    for k in keys:
        if isinstance(k, str) and "balance" in k.lower():
            continue
        # skip obvious description columns to avoid postal codes being parsed as amounts
        if isinstance(k, str) and any(
            p in k.lower()
            for p in (
                "booking",
                "booking text",
                "booking text ",
                "payment",
                "purpose",
                "details",
                "reference",
            )
        ):
            # still allow if the value contains a decimal separator (likely an amount)
            v = rec.get(k)
            if isinstance(v, str) and ("." in v or "," in v):
                num = _to_float(v)
                if num is not None:
                    if "credit" in k.lower():
                        return num, "credit"
                    if "debit" in k.lower():
                        return num, "debit"
                    return num, None
            continue
        v = rec.get(k)
        num = _to_float(v)
        if num is not None:
            # skip implausibly large values discovered in other columns
            if abs(num) >= MAX_SCAN_AMOUNT:
                continue
            # guess kind: if column name contains credit/debit
            if isinstance(k, str) and "credit" in k.lower():
                return num, "credit"
            if isinstance(k, str) and "debit" in k.lower():
                return num, "debit"
            return num, None
    return None, None


def _to_float(v):
    if pd.isna(v):
        return None
    try:
        if isinstance(v, str):
            s = v.replace("\u00a0", " ").strip()
            s = " ".join(s.split())
            import re

            # reject postal-code like tokens (e.g. CH-8004) which commonly appear in addresses
            if re.search(r"\b[A-Za-z]{1,3}-\d{3,5}\b", s):
                return None
            # Normalize mixed separators: if both '.' and ',' present, determine which is decimal
            if "." in s and "," in s:
                if s.rfind(",") > s.rfind("."):
                    # comma appears later => comma is decimal separator
                    s = s.replace(".", "")
                    s = s.replace(",", ".")
                else:
                    # dot is decimal separator, remove commas
                    s = s.replace(",", "")
            elif "," in s and "." not in s:
                # single comma => treat as decimal
                s = s.replace(",", ".")

            # find simple numeric tokens (integer or decimal)
            matches = re.findall(r"[-+]?\d+(?:\.\d+)?", s)
            if not matches:
                return None
            # prefer a match that contains a decimal point (monetary amounts), otherwise first
            chosen = next((m for m in matches if "." in m), matches[0])
            return float(chosen)
        # non-string values
        return float(v)
    except Exception:
        return None


def _extract_reference_from_desc(desc: str) -> str:
    # simplistic: look for tokens like 'Transfer to' or 'Transfer from' or 'Top-up by *xxxx'
    if not isinstance(desc, str):
        return None
    return desc


PARSERS = [
    ("revolut", parse_revolut),
    ("zkb", parse_zkb),
]


def detect_and_parse(path: Path) -> pd.DataFrame:
    # Read file and detect delimiter/format, then route to the appropriate parser.
    text = path.read_text(encoding="utf-8", errors="replace")
    # Heuristics: semicolon -> zkb, comma -> revolut
    semicolon = False
    try:
        first_line = text.splitlines()[0]
        semicolon = ";" in first_line
    except Exception:
        semicolon = False
    # read CSV using conservative options
    try:
        if semicolon:
            try:
                df = pd.read_csv(
                    path, sep=";", quotechar='"', encoding="utf-8", dtype=str
                )
            except Exception:
                df = pd.read_csv(
                    path,
                    sep=";",
                    quotechar='"',
                    engine="python",
                    encoding="utf-8",
                    dtype=str,
                )
        else:
            df = pd.read_csv(path, quotechar='"', encoding="utf-8", dtype=str)
    except Exception as e:
        # If we couldn't read the file as CSV, return an empty dataframe to avoid crashes
        print(f"Warning: could not read {path} as CSV: {e}", file=sys.stderr)
        return pd.DataFrame()

    cols = [c.strip() for c in df.columns]
    df.columns = cols

    # If this was a semicolon (ZKB) file, expand Mobile Banking summary rows so child rows inherit the date
    if semicolon and "Date" in df.columns:
        df = expand_mobile_summaries_in_df(df)

    # decide parser
    header = " ".join(cols).lower()
    if any("amount" in c.lower() for c in cols) and "started date" in header:
        return parse_revolut(df)
    if (
        ("zkb" in header)
        or ("z kb" in str(path.name).lower())
        or ("Date" in cols and ("Debit CHF" in cols or "Credit CHF" in cols))
    ):
        return parse_zkb(df)

    # fallback: try to guess by presence of Amount+Currency
    if "Amount" in cols and "Currency" in cols:
        return parse_revolut(df)

    # generic fallback mapping -> produce minimal normalized-like DataFrame
    out = pd.DataFrame()
    # try to find a date-like column and map to value_date
    date_col = None
    for c in cols:
        if "date" in c.lower():
            date_col = c
            break
    if date_col:
        out["value_date"] = df[date_col].apply(lambda v: _parse_date(v, dayfirst=True))
    else:
        out["value_date"] = None
    # description
    desc_col = None
    for c in cols:
        if "desc" in c.lower() or "booking" in c.lower() or "description" in c.lower():
            desc_col = c
            break
    out["description"] = df[desc_col] if desc_col else df.iloc[:, 0].astype(str)
    # amount
    amt = None
    for c in cols:
        if "amount" in c.lower() or "debit" in c.lower() or "credit" in c.lower():
            amt = c
            break
    if amt:
        out["amount"] = df[amt].apply(_to_float)
    else:
        out["amount"] = None
    # currency
    currency_col = None
    for c in cols:
        if "curr" in c.lower() or "currency" in c.lower():
            currency_col = c
            break
    out["currency"] = df[currency_col] if currency_col else None
    out["fee"] = None
    out["reference"] = None
    out["type"] = None
    return out


def expand_mobile_summaries_in_df(df: pd.DataFrame) -> pd.DataFrame:
    import re

    mobile_re = re.compile(r"mobile banking\s*\((\d+)\)", flags=re.I)
    records = df.to_dict(orient="records")
    out_records: list[dict] = []
    i = 0
    while i < len(records):
        row = records[i]
        # pick booking text from common columns
        booking = ""
        for k in (
            "Booking text",
            "Booking text ",
            "Payment purpose",
            "Payment Purpose",
        ):
            if k in row and row.get(k) and str(row.get(k)).strip() != "":
                booking = str(row.get(k))
                break
        if booking:
            m = mobile_re.search(booking)
            if m:
                try:
                    n = int(m.group(1))
                except Exception:
                    n = 0
                # collect next up-to-n rows and give them the parent's Date
                parent_date = row.get("Date") if "Date" in row else None
                parent_lower = booking.lower()
                parent_is_debit = (
                    "debit" in parent_lower and "credit" not in parent_lower
                )
                children = []
                parent_value_date = (
                    row.get("Value date") if "Value date" in row else None
                )
                for j in range(i + 1, min(i + 1 + n, len(records))):
                    child = records[j].copy()
                    # set child's Date to parent's Date and Value date to parent's Value date (if present)
                    if parent_date:
                        child["Date"] = parent_date
                    if parent_value_date:
                        child["Value date"] = parent_value_date
                    # if child already has explicit Debit/Credit, keep it; otherwise try to populate from Amount details
                    if (not child.get("Debit CHF")) and (not child.get("Credit CHF")):
                        # try common amount fields
                        amt = None
                        for ak in ("Amount details", "Amount", "Amt"):
                            if (
                                ak in child
                                and child.get(ak)
                                and str(child.get(ak)).strip() != ""
                            ):
                                amt = _to_float(child.get(ak))
                                break
                        # if we found an amount and parent indicates debit/credit, write the appropriate column
                        if amt is not None:
                            if parent_is_debit:
                                child["Debit CHF"] = str(amt)
                                child["Credit CHF"] = ""
                            else:
                                child["Credit CHF"] = str(amt)
                                child["Debit CHF"] = ""
                    children.append(child)
                # append children in place of parent
                if children:
                    out_records.extend(children)
                    i = i + 1 + len(children)
                    continue
        # default: keep original row
        out_records.append(row)
        i += 1
    return pd.DataFrame(out_records)

    # If this was a semicolon (ZKB) file, expand Mobile Banking summary rows so child rows inherit the date
    if semicolon and "Date" in df.columns:
        df = expand_mobile_summaries_in_df(df)
    # decide parser
    header = " ".join(cols).lower()
    if any("amount" in c.lower() for c in cols) and "started date" in header:
        return parse_revolut(df)
    if (
        "z kb" in str(path.name).lower()
        or "zkb" in header
        or ("date" in cols and "Debit CHF" in cols)
        or ("Debit CHF" in cols or "Credit CHF" in cols)
    ):
        return parse_zkb(df)
    # fallback: try to detect by columns
    if "Amount" in cols and "Currency" in cols:
        return parse_revolut(df)
    # fallback generic mapping
    out = pd.DataFrame()
    out["source_file"] = path.name
    # try to find a date-like column
    date_col = None
    for c in cols:
        if "date" in c.lower():
            date_col = c
            break
    if date_col:
        out["booking_date"] = df[date_col].apply(
            lambda v: _parse_date(v, dayfirst=True)
        )
    else:
        out["booking_date"] = None
    # description
    desc_col = None
    for c in cols:
        if "desc" in c.lower() or "booking" in c.lower() or "description" in c.lower():
            desc_col = c
            break
    out["description"] = df[desc_col] if desc_col else df.iloc[:, 0].astype(str)
    # amount
    amt = None
    for c in cols:
        if "amount" in c.lower() or "debit" in c.lower() or "credit" in c.lower():
            amt = c
            break
    if amt:
        out["amount"] = df[amt].apply(_to_float)
    else:
        out["amount"] = None
    out["currency"] = None
    out["fee"] = None
    out["balance"] = None
    out["reference"] = None
    return out


def normalize_folder(input_dir: str, output_dir: str, preview: int = 0):
    inp = Path(input_dir)
    outp = Path(output_dir)
    outp.mkdir(parents=True, exist_ok=True)
    files = sorted(
        [
            p
            for p in inp.iterdir()
            if p.is_file() and p.suffix.lower() in (".csv", ".txt")
        ]
    )
    summary = []
    for p in files:
        try:
            df_norm = detect_and_parse(p)
            # ensure OUT_COLS exist
            for c in OUT_COLS:
                if c not in df_norm.columns:
                    df_norm[c] = None
            df_norm = df_norm[OUT_COLS]
            dest = outp / f"normalized_{p.name}"
            df_norm.to_csv(dest, index=False, encoding="utf-8")
            summary.append((p.name, len(df_norm), str(dest)))
            if preview > 0:
                print(
                    f"Preview for {p.name} -> {dest}:\n",
                    df_norm.head(preview).to_string(index=False, justify="left"),
                )
        except Exception as e:
            print(f"Failed processing {p}: {e}", file=sys.stderr)
    print("Written files:")
    for s in summary:
        print(f" - {s[0]}: {s[1]} rows -> {s[2]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input-dir",
        default="original",
        help="Input directory with original statements",
    )
    ap.add_argument(
        "--output-dir",
        default="normalized",
        help="Output directory for normalized CSVs",
    )
    ap.add_argument("--preview", type=int, default=0, help="Show a small preview")
    args = ap.parse_args()
    normalize_folder(args.input_dir, args.output_dir, args.preview)


if __name__ == "__main__":
    main()
