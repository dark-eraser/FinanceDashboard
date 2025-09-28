def expenses_by_category(request):
    from .models import Transaction, UploadedFile

    file_ids = request.GET.getlist("file")
    files = UploadedFile.objects.all().order_by("-uploaded_at")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    qs = Transaction.objects.all()
    if file_ids:
        qs = qs.filter(uploaded_file_id__in=file_ids)
    # Filter by date range if provided
    if start_date:
        qs = qs.filter(date__gte=start_date)
    if end_date:
        qs = qs.filter(date__lte=end_date)
    transactions_qs = qs
    transactions = [
        {
            "Date": t.date,
            "Booking_text": t.booking_text,
            "Category": t.category,
            "Amount": t.amount,
        }
        for t in transactions_qs
    ]
    from collections import defaultdict

    category_totals = defaultdict(float)
    for tx in transactions:
        category = tx.get("Category", "Unknown")
        amt = tx.get("Amount", 0)
        if isinstance(amt, (float, int)):
            amount = amt if amt is not None else 0.0
        else:
            try:
                amount_clean = str(amt).replace(",", "").strip()
                amount = (
                    float(amount_clean)
                    if amount_clean and amount_clean.lower() != "nan"
                    else 0.0
                )
            except Exception:
                amount = 0.0
        category_totals[category] += amount
    labels = list(category_totals.keys())
    amounts = list(category_totals.values())
    import json

    # Prepare filtered category totals for JS (exclude 'Uncounted')
    filtered_category_totals = {
        k: v for k, v in category_totals.items() if k != "Uncounted"
    }

    # Prepare table data for template
    category_table = zip(labels, amounts)
    return render(
        request,
        "dashboard/expenses_by_category.html",
        {
            "labels": json.dumps(labels),
            "amounts": json.dumps(amounts),
            "category_table": category_table,
            "transactions": transactions,
            "files": files,
            "selected_file_ids": [str(fid) for fid in file_ids],
            "start_date": start_date,
            "end_date": end_date,
            "filtered_category_totals": filtered_category_totals,
            "filtered_category_totals_json": json.dumps(filtered_category_totals),
        },
    )


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
        from .models import Transaction, UploadedFile

        # Create a new UploadedFile record for this upload
        uploaded_file = UploadedFile.objects.create(name=file.name)
        for tx in transactions:
            Transaction.objects.create(
                uploaded_file=uploaded_file,
                date=tx.get("Date", ""),
                booking_text=tx.get("Booking_text", ""),
                category=tx.get("Category", ""),
                amount=float(tx.get("Amount", 0) or 0),
            )
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
