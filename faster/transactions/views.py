import pandas as pd
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt


def dashboard(request):
    transactions = []
    error = None
    zkb_cols = ["date", "booking text", "category", "debit chf"]
    revolut_required = ["completed date", "description", "category", "amount"]
    if request.method == "POST" and request.FILES.get("csv_file"):
        # Try both separators, resetting file pointer each time
        file = request.FILES["csv_file"]
        df = None
        import io

        # Read file as text
        file.seek(0)
        file_content = file.read()
        if isinstance(file_content, bytes):
            file_content = file_content.decode("utf-8-sig")
        # Debug: print first line of file
        first_line = file_content.splitlines()[0] if file_content else ""
        print(f"First line of CSV: {first_line}")
        # Try auto-detecting separator first
        try:
            df = pd.read_csv(
                io.StringIO(file_content), sep=None, engine="python", dtype=str
            )
            df.columns = [c.strip() for c in df.columns]
        except Exception:
            df = None
        # If auto-detect fails, try explicit separators
        if df is None:
            for sep in [";", ","]:
                try:
                    df = pd.read_csv(io.StringIO(file_content), sep=sep, dtype=str)
                    df.columns = [c.strip() for c in df.columns]
                    break
                except Exception:
                    df = None
                    continue
        if df is not None:
            # Normalize columns for matching
            norm_cols = [c.strip().lower() for c in df.columns]
            # Debug: print normalized columns to error for troubleshooting
            print(f"Normalized columns: {norm_cols}")
        if df is None:
            error = "Could not read CSV file."
        else:
            # Try ZKB format first (case/whitespace-insensitive)
            if all(col in norm_cols for col in zkb_cols):
                rename_map = {}
                for orig in df.columns:
                    norm = orig.strip().lower()
                    if norm == "booking text":
                        rename_map[orig] = "Booking_text"
                    elif norm == "category":
                        rename_map[orig] = "Category"
                    elif norm == "date":
                        rename_map[orig] = "Date"
                    elif norm == "debit chf":
                        rename_map[orig] = "Amount"
                df = df.rename(columns=rename_map)
                transactions = df[
                    ["Date", "Booking_text", "Category", "Amount"]
                ].to_dict(orient="records")
            # Try Revolut format (case/whitespace-insensitive)
            elif all(col in norm_cols for col in revolut_required):
                rename_map = {}
                for orig in df.columns:
                    norm = orig.strip().lower()
                    if norm == "completed date":
                        rename_map[orig] = "Date"
                    elif norm == "description":
                        rename_map[orig] = "Booking_text"
                    elif norm == "category":
                        rename_map[orig] = "Category"
                    elif norm == "amount":
                        rename_map[orig] = "Amount"
                df = df.rename(columns=rename_map)
                transactions = df[
                    ["Date", "Booking_text", "Category", "Amount"]
                ].to_dict(orient="records")
            # Flexible custom format: only require key columns (set-based)
            elif set(["completed date", "description", "category", "amount"]).issubset(
                set(norm_cols)
            ):
                rename_map = {}
                for orig in df.columns:
                    norm = orig.strip().lower()
                    if norm == "completed date":
                        rename_map[orig] = "Date"
                    elif norm == "description":
                        rename_map[orig] = "Booking_text"
                    elif norm == "category":
                        rename_map[orig] = "Category"
                    elif norm == "amount":
                        rename_map[orig] = "Amount"
                df = df.rename(columns=rename_map)
                # Only select columns that exist
                selected_cols = [
                    col
                    for col in ["Date", "Booking_text", "Category", "Amount"]
                    if col in df.columns
                ]
                transactions = df[selected_cols].to_dict(orient="records")
            else:
                error = f"CSV format not recognized. Columns found: {', '.join(df.columns)}. Please upload a ZKB, Revolut, or supported export."
    # Save transactions in session for analytics/dashboard use
    if transactions:
        request.session["transactions"] = transactions
    return render(
        request,
        "transactions/dashboard.html",
        {"transactions": transactions, "error": error},
    )


import json

from django.http import JsonResponse


def analytics_dashboard(request):
    # For demo: load transactions from session if available
    transactions = request.session.get("transactions", [])
    # Aggregate by category
    from collections import defaultdict

    category_totals = defaultdict(float)
    for tx in transactions:
        try:
            category = tx.get("Category", "Unknown")
            amount = float(tx.get("Amount", 0))
            category_totals[category] += amount
        except Exception:
            continue
    labels = list(category_totals.keys())
    amounts = list(category_totals.values())
    return render(
        request,
        "dashboard/analytics.html",
        {
            "labels": json.dumps(labels),
            "amounts": json.dumps(amounts),
        },
    )
