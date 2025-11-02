def settings_view(request):
    """Settings view for managing data sources, currencies, and uploads"""
    import json

    from .models import Transaction, UploadedFile

    files = UploadedFile.objects.all().order_by("-uploaded_at")
    all_currencies = sorted(
        set(t.currency for t in Transaction.objects.all() if t.currency)
    )

    # Get current settings from session
    selected_file_ids = request.session.get("selected_file_ids", [])
    selected_currencies = request.session.get("selected_currencies", [])

    error = None
    success = None

    # Handle file upload
    if request.method == "POST" and "csv_file" in request.FILES:
        csv_file = request.FILES["csv_file"]

        try:
            import io

            import pandas as pd

            content = csv_file.read().decode("utf-8")

            # Try different separators
            df = None
            for sep in [";", ",", None]:
                try:
                    df = pd.read_csv(io.StringIO(content), sep=sep)
                    if len(df.columns) > 1:
                        break
                except Exception:
                    continue

            if df is None or len(df.columns) <= 1:
                error = "Could not parse CSV file"
            else:
                # Normalize column names
                df.columns = [col.strip() for col in df.columns]

                # Expand ZKB child transactions (rows with empty Date field)
                # ZKB statements have grouped transactions like "Debit Mobile Banking (3)" where
                # child transactions have empty Date and need to inherit parent's date
                if "Date" in df.columns:
                    current_date = None
                    for idx in df.index:
                        date_val = str(
                            df.at[idx, "Date"] if pd.notna(df.at[idx, "Date"]) else ""
                        ).strip()

                        if date_val and date_val != "Date":
                            current_date = date_val
                        elif current_date:
                            # Child transaction - inherit parent's date
                            df.at[idx, "Date"] = current_date

                            # Also populate amount from Amount details if present
                            if "Amount details" in df.columns and "Curr" in df.columns:
                                amount_str = str(
                                    df.at[idx, "Amount details"]
                                    if pd.notna(df.at[idx, "Amount details"])
                                    else ""
                                ).strip()
                                curr = str(
                                    df.at[idx, "Curr"]
                                    if pd.notna(df.at[idx, "Curr"])
                                    else ""
                                ).strip()

                                if amount_str and curr == "CHF":
                                    debit_empty = (
                                        pd.isna(df.at[idx, "Debit CHF"])
                                        or str(df.at[idx, "Debit CHF"]).strip() == ""
                                    )
                                    credit_empty = (
                                        pd.isna(df.at[idx, "Credit CHF"])
                                        or str(df.at[idx, "Credit CHF"]).strip() == ""
                                    )

                                    if debit_empty and credit_empty:
                                        df.at[idx, "Debit CHF"] = amount_str

                # Create UploadedFile record
                uploaded_file = UploadedFile.objects.create(name=csv_file.name)

                # Map columns based on different CSV formats
                transactions_to_create = []

                for _, row in df.iterrows():
                    # Extract date
                    date_val = (
                        row.get("Date")
                        or row.get("value_date")
                        or row.get("Started Date")
                        or ""
                    )

                    # Extract description
                    booking_text = (
                        row.get("Booking text")
                        or row.get("description")
                        or row.get("Description")
                        or ""
                    )

                    # Extract category
                    category = row.get("Category") or ""

                    # Extract amount
                    amount = None
                    if "Debit CHF" in row and pd.notna(row["Debit CHF"]):
                        amount = -abs(float(row["Debit CHF"]))
                    elif "Credit CHF" in row and pd.notna(row["Credit CHF"]):
                        amount = abs(float(row["Credit CHF"]))
                    elif "amount" in row and pd.notna(row["amount"]):
                        amount = float(row["amount"])
                    elif "Amount" in row and pd.notna(row["Amount"]):
                        amount = float(row["Amount"])

                    # Extract currency
                    currency = (
                        row.get("curr")
                        or row.get("currency")
                        or row.get("Currency")
                        or ""
                    )

                    transactions_to_create.append(
                        Transaction(
                            date=str(date_val),
                            booking_text=str(booking_text),
                            category=str(category),
                            amount=amount,
                            currency=str(currency),
                            uploaded_file=uploaded_file,
                        )
                    )

                Transaction.objects.bulk_create(transactions_to_create)
                success = f"Successfully uploaded {len(transactions_to_create)} transactions from {csv_file.name}"

                # Refresh files list
                files = UploadedFile.objects.all().order_by("-uploaded_at")
                all_currencies = sorted(
                    set(t.currency for t in Transaction.objects.all() if t.currency)
                )

        except Exception as e:
            error = f"Error processing file: {str(e)}"

    # Handle settings update
    elif request.method == "POST":
        selected_file_ids = request.POST.getlist("file")
        selected_currencies = request.POST.getlist("currency")

        # Save to session
        request.session["selected_file_ids"] = selected_file_ids
        request.session["selected_currencies"] = selected_currencies

        success = "Settings saved successfully"

    return render(
        request,
        "dashboard/settings.html",
        {
            "files": files,
            "all_currencies": all_currencies,
            "selected_file_ids": selected_file_ids,
            "selected_currencies": selected_currencies,
            "error": error,
            "success": success,
        },
    )


def expenses_vs_income(request):
    from .models import Transaction, UploadedFile

    # Get filters from session instead of GET parameters
    selected_file_ids = request.session.get("selected_file_ids", [])
    selected_currencies = request.session.get("selected_currencies", [])

    files = UploadedFile.objects.all().order_by("-uploaded_at")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    qs = Transaction.objects.all()
    if selected_file_ids:
        qs = qs.filter(uploaded_file_id__in=selected_file_ids)
    transactions = list(qs)

    # Get unique currencies for dropdown
    all_currencies = sorted(
        {t.currency for t in Transaction.objects.all() if t.currency}
    )

    # Python-side date filtering for string dates
    import datetime

    def parse_date(date_str):
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.datetime.strptime(date_str, fmt).date()
            except Exception:
                continue
        return None

    if start_date:
        start_dt = parse_date(start_date)
        transactions = [
            t
            for t in transactions
            if parse_date(t.date) and parse_date(t.date) >= start_dt
        ]
    if end_date:
        end_dt = parse_date(end_date)
        transactions = [
            t
            for t in transactions
            if parse_date(t.date) and parse_date(t.date) <= end_dt
        ]

    # Filter by currencies if selected in session
    if selected_currencies:
        transactions = [t for t in transactions if t.currency in selected_currencies]

    # Get unique categories for checkboxes
    from collections import defaultdict

    category_totals = defaultdict(float)
    for t in transactions:
        category = t.category if t.category else "Uncounted"
        if category not in category_totals:
            category_totals[category] = 0.0
        try:
            category_totals[category] += float(t.amount) if t.amount else 0.0
        except Exception:
            pass

    # Filter out 'Uncounted' for display
    filtered_category_totals = {
        k: v for k, v in category_totals.items() if k != "Uncounted"
    }

    # Aggregate expenses and income
    expenses = sum(t.amount for t in transactions if t.amount and t.amount < 0)
    income = sum(t.amount for t in transactions if t.amount and t.amount > 0)

    # Prepare for chart
    chart_data = {
        "labels": ["Expenses", "Income"],
        "amounts": [abs(expenses), income],
    }
    # Prepare transactions for table
    tx_data = [
        {
            "Date": t.date,
            "Booking_text": t.booking_text,
            "Category": t.category,
            "Amount": t.amount,
            "Currency": t.currency,
        }
        for t in transactions
    ]
    import json

    return render(
        request,
        "dashboard/expenses_vs_income.html",
        {
            "chart_data": json.dumps(chart_data),
            "transactions": tx_data,
            "files": files,
            "selected_file_ids": selected_file_ids,
            "start_date": start_date,
            "end_date": end_date,
            "filtered_category_totals": filtered_category_totals,
            "all_currencies": all_currencies,
            "selected_currencies": selected_currencies,
        },
    )


def expenses_by_category(request):
    from .models import Transaction, UploadedFile

    # Get filters from session
    selected_file_ids = request.session.get("selected_file_ids", [])
    selected_currencies = request.session.get("selected_currencies", [])

    files = UploadedFile.objects.all().order_by("-uploaded_at")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    qs = Transaction.objects.all()
    if selected_file_ids:
        qs = qs.filter(uploaded_file_id__in=selected_file_ids)

    # Get unique currencies for dropdown
    all_currencies = sorted(
        {t.currency for t in Transaction.objects.all() if t.currency}
    )

    # Filter by date range if provided
    if start_date:
        qs = qs.filter(date__gte=start_date)
    if end_date:
        qs = qs.filter(date__lte=end_date)

    # Filter by currencies if selected in session
    if selected_currencies:
        qs = qs.filter(currency__in=selected_currencies)

    transactions_qs = qs
    # Filter to only include expenses (negative amounts) and convert to positive
    transactions = [
        {
            "Date": t.date,
            "Booking_text": t.booking_text,
            "Category": t.category,
            "Amount": abs(t.amount),  # Convert to positive for display
            "Currency": t.currency,
        }
        for t in transactions_qs
        if t.amount is not None and t.amount < 0
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
        category_totals[category] += abs(amount)  # Store as positive
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
            "selected_file_ids": selected_file_ids,
            "start_date": start_date,
            "end_date": end_date,
            "filtered_category_totals": filtered_category_totals,
            "filtered_category_totals_json": json.dumps(filtered_category_totals),
            "all_currencies": all_currencies,
            "selected_currencies": selected_currencies,
        },
    )


def income_by_category(request):
    from .models import Transaction, UploadedFile

    # Get filters from session
    selected_file_ids = request.session.get("selected_file_ids", [])
    selected_currencies = request.session.get("selected_currencies", [])

    files = UploadedFile.objects.all().order_by("-uploaded_at")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    qs = Transaction.objects.all()
    if selected_file_ids:
        qs = qs.filter(uploaded_file_id__in=selected_file_ids)

    # Get unique currencies for dropdown
    all_currencies = sorted(
        {t.currency for t in Transaction.objects.all() if t.currency}
    )

    # Filter by date range if provided
    if start_date:
        qs = qs.filter(date__gte=start_date)
    if end_date:
        qs = qs.filter(date__lte=end_date)

    # Filter by currencies if selected in session
    if selected_currencies:
        qs = qs.filter(currency__in=selected_currencies)

    transactions_qs = qs
    # Filter to only include income (positive amounts)
    transactions = [
        {
            "Date": t.date,
            "Booking_text": t.booking_text,
            "Category": t.category,
            "Amount": t.amount,  # Already positive
            "Currency": t.currency,
        }
        for t in transactions_qs
        if t.amount is not None and t.amount > 0
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
        "dashboard/income_by_category.html",
        {
            "labels": json.dumps(labels),
            "amounts": json.dumps(amounts),
            "category_table": category_table,
            "transactions": transactions,
            "files": files,
            "selected_file_ids": selected_file_ids,
            "start_date": start_date,
            "end_date": end_date,
            "filtered_category_totals": filtered_category_totals,
            "filtered_category_totals_json": json.dumps(filtered_category_totals),
            "all_currencies": all_currencies,
            "selected_currencies": selected_currencies,
        },
    )


import pandas as pd
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt


def dashboard(request):
    from collections import defaultdict

    from .models import Transaction, UploadedFile

    # Get filters from session
    selected_file_ids = request.session.get("selected_file_ids", [])
    selected_currencies = request.session.get("selected_currencies", [])

    # Filter transactions based on session settings
    qs = Transaction.objects.all()
    if selected_file_ids:
        qs = qs.filter(uploaded_file_id__in=selected_file_ids)
    if selected_currencies:
        qs = qs.filter(currency__in=selected_currencies)

    all_transactions = list(qs)

    # Calculate top spending categories (negative amounts) with currency breakdown
    expense_by_category_currency = defaultdict(lambda: defaultdict(float))
    for t in all_transactions:
        if t.amount and t.amount < 0 and t.category and t.category != "Uncounted":
            currency = t.currency if t.currency else "Unknown"
            expense_by_category_currency[t.category][currency] += abs(t.amount)

    # Convert to list with total and currency breakdown
    top_spending = []
    for category, currency_amounts in expense_by_category_currency.items():
        total = sum(currency_amounts.values())
        top_spending.append(
            {"category": category, "total": total, "currencies": dict(currency_amounts)}
        )

    # Sort by total and get top 5
    top_spending = sorted(top_spending, key=lambda x: x["total"], reverse=True)[:5]

    # Calculate top income categories (positive amounts) with currency breakdown
    income_by_category_currency = defaultdict(lambda: defaultdict(float))
    for t in all_transactions:
        if t.amount and t.amount > 0 and t.category and t.category != "Uncounted":
            currency = t.currency if t.currency else "Unknown"
            income_by_category_currency[t.category][currency] += t.amount

    # Convert to list with total and currency breakdown
    top_income = []
    for category, currency_amounts in income_by_category_currency.items():
        total = sum(currency_amounts.values())
        top_income.append(
            {"category": category, "total": total, "currencies": dict(currency_amounts)}
        )

    # Sort by total and get top 5
    top_income = sorted(top_income, key=lambda x: x["total"], reverse=True)[:5]

    # Prepare recent transactions for display (last 50)
    transactions = [
        {
            "Date": t.date,
            "Booking_text": t.booking_text,
            "Category": t.category,
            "Amount": t.amount,
            "Currency": t.currency,
        }
        for t in all_transactions[:50]
    ]

    return render(
        request,
        "transactions/dashboard.html",
        {
            "transactions": transactions,
            "top_spending": top_spending,
            "top_income": top_income,
        },
    )


import json


def delete_file(request, file_id):
    """Delete an uploaded file and all its associated transactions"""
    from django.shortcuts import redirect

    from .models import UploadedFile

    if request.method == "POST":
        try:
            uploaded_file = UploadedFile.objects.get(id=file_id)
            uploaded_file.delete()  # This will cascade delete all related transactions
        except UploadedFile.DoesNotExist:
            pass

    # Redirect back to the referrer or dashboard
    return redirect(request.META.get("HTTP_REFERER", "/"))
