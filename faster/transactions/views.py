"""Helper functions for dashboard views"""


def get_excluded_categories():
    """Get list of excluded categories from dashboard settings"""
    try:
        from .models import DashboardSettings

        return DashboardSettings.get_excluded_categories()
    except Exception:
        return []


def filter_transactions_by_excluded_categories(transactions, excluded_categories=None):
    """Filter out transactions with excluded categories"""
    if excluded_categories is None:
        excluded_categories = get_excluded_categories()

    return [t for t in transactions if t.category not in excluded_categories]


def filter_category_totals_by_excluded(category_totals, excluded_categories=None):
    """Remove excluded categories from category totals"""
    if excluded_categories is None:
        excluded_categories = get_excluded_categories()

    return {k: v for k, v in category_totals.items() if k not in excluded_categories}


def settings_view(request):
    """Settings view for managing data sources, currencies, and uploads"""
    import json

    from .models import DashboardSettings, Transaction, UploadedFile

    files = UploadedFile.objects.all().order_by("-uploaded_at")
    all_currencies = sorted(
        set(t.currency for t in Transaction.objects.all() if t.currency)
    )

    # Get excluded categories from database
    dashboard_settings = DashboardSettings.get_settings()
    excluded_categories = dashboard_settings.excluded_categories or []

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
                    # Handle pandas NaN values
                    if pd.isna(category):
                        category = ""

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

                # Create transactions
                created_transactions = Transaction.objects.bulk_create(
                    transactions_to_create
                )

                # Apply semantic categorization to newly created transactions
                try:
                    from .categorization_service import TransactionCategorizationService

                    categorization_service = TransactionCategorizationService()

                    # Get the actual created transactions (bulk_create doesn't return IDs in older Django versions)
                    new_transactions = Transaction.objects.filter(
                        uploaded_file=uploaded_file
                    )

                    # Categorize transactions that don't already have categories
                    uncategorized = [
                        t
                        for t in new_transactions
                        if not t.category or t.category in ["Uncategorized", "nan"]
                    ]

                    if uncategorized:
                        categorization_stats = (
                            categorization_service.categorize_transactions_bulk(
                                uncategorized
                            )
                        )
                        success = (
                            f"Successfully uploaded {len(transactions_to_create)} transactions from {csv_file.name}. "
                            f"Automatically categorized {categorization_stats['categorized']} transactions using semantic analysis "
                            f"({categorization_stats['high_confidence']} high confidence, "
                            f"{categorization_stats['medium_confidence']} medium confidence)."
                        )
                    else:
                        success = f"Successfully uploaded {len(transactions_to_create)} transactions from {csv_file.name}"

                except Exception as e:
                    # If categorization fails, still show success for upload
                    success = f"Successfully uploaded {len(transactions_to_create)} transactions from {csv_file.name}. Note: Automatic categorization failed: {str(e)}"

                # Refresh files list
                files = UploadedFile.objects.all().order_by("-uploaded_at")
                all_currencies = sorted(
                    set(t.currency for t in Transaction.objects.all() if t.currency)
                )

        except Exception as e:
            import traceback

            error_msg = f"Error processing file: {str(e)}\n{traceback.format_exc()}"
            print(f"[ERROR] {error_msg}", flush=True)
            error = f"Error processing file: {str(e)}"

    # Handle settings update
    elif request.method == "POST":
        selected_file_ids = request.POST.getlist("file")
        selected_currencies = request.POST.getlist("currency")

        # Save to session
        request.session["selected_file_ids"] = selected_file_ids
        request.session["selected_currencies"] = selected_currencies

        success = "Settings saved successfully"

    # Get all unique categories for the category management section
    all_categories = sorted(
        set(
            t.category
            for t in Transaction.objects.all()
            if t.category and t.category != "Uncounted"
        )
    )

    return render(
        request,
        "transactions/settings.html",
        {
            "files": files,
            "all_currencies": all_currencies,
            "all_categories": all_categories,
            "selected_file_ids": selected_file_ids,
            "selected_currencies": selected_currencies,
            "excluded_categories": excluded_categories,
            "error": error,
            "success": success,
        },
    )


def expenses_vs_income(request):
    import datetime

    from .models import Transaction, UploadedFile

    # Get filters from session instead of GET parameters
    selected_file_ids = request.session.get("selected_file_ids", [])
    selected_currencies = request.session.get("selected_currencies", [])

    files = UploadedFile.objects.all().order_by("-uploaded_at")

    qs = Transaction.objects.all()
    if selected_file_ids:
        qs = qs.filter(uploaded_file_id__in=selected_file_ids)
    transactions = list(qs)

    # Get unique currencies for dropdown
    all_currencies = sorted(
        {t.currency for t in Transaction.objects.all() if t.currency}
    )

    # Python-side date filtering for string dates
    def parse_date(date_str):
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.datetime.strptime(date_str, fmt).date()
            except Exception:
                continue
        return None

    # Apply time filter (takes precedence over manual date range)
    time_filter = request.GET.get("time_filter", "all")
    custom_start = request.GET.get("start_date") if time_filter == "custom" else None
    custom_end = request.GET.get("end_date") if time_filter == "custom" else None

    # Filter by time period
    filtered_transactions = []
    today = datetime.date.today()

    for t in transactions:
        transaction_date = parse_date(t.date)
        if not transaction_date:
            continue

        include = False

        if time_filter == "all":
            include = True
        elif time_filter == "last_year":
            one_year_ago = today - datetime.timedelta(days=365)
            include = transaction_date >= one_year_ago
        elif time_filter == "custom" and custom_start and custom_end:
            start_dt = parse_date(custom_start)
            end_dt = parse_date(custom_end)
            if start_dt and end_dt:
                include = start_dt <= transaction_date <= end_dt

        if include:
            filtered_transactions.append(t)

    transactions = filtered_transactions

    # Filter by currencies if selected in session
    if selected_currencies:
        transactions = [t for t in transactions if t.currency in selected_currencies]

    # Filter out excluded categories
    excluded_categories = get_excluded_categories()
    transactions = filter_transactions_by_excluded_categories(
        transactions, excluded_categories
    )

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
            "start_date": custom_start if time_filter == "custom" else "",
            "end_date": custom_end if time_filter == "custom" else "",
            "filtered_category_totals": filtered_category_totals,
            "all_currencies": all_currencies,
            "selected_currencies": selected_currencies,
        },
    )


def expenses_by_category(request):
    import datetime

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

    # Apply time filter (takes precedence over manual date range)
    time_filter = request.GET.get("time_filter", "all")
    custom_start = request.GET.get("start_date") if time_filter == "custom" else None
    custom_end = request.GET.get("end_date") if time_filter == "custom" else None

    # Helper function to parse date strings
    def parse_date(date_str):
        if not date_str:
            return None
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.datetime.strptime(date_str, fmt).date()
            except Exception:
                continue
        return None

    # Get all transactions first
    all_transactions = list(qs)

    # Filter by time period
    filtered_transactions = []
    today = datetime.date.today()

    for t in all_transactions:
        transaction_date = parse_date(t.date)
        if not transaction_date:
            continue

        include = False

        if time_filter == "all":
            include = True
        elif time_filter == "last_year":
            one_year_ago = today - datetime.timedelta(days=365)
            include = transaction_date >= one_year_ago
        elif time_filter == "custom" and custom_start and custom_end:
            start_dt = parse_date(custom_start)
            end_dt = parse_date(custom_end)
            if start_dt and end_dt:
                include = start_dt <= transaction_date <= end_dt

        if include:
            filtered_transactions.append(t)

    # Filter by currencies if selected in session
    if selected_currencies:
        filtered_transactions = [
            t for t in filtered_transactions if t.currency in selected_currencies
        ]

    # Filter out excluded categories
    excluded_categories = get_excluded_categories()
    filtered_transactions = filter_transactions_by_excluded_categories(
        filtered_transactions, excluded_categories
    )

    transactions_qs = filtered_transactions
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
    import datetime

    from .models import Transaction, UploadedFile

    # Get filters from session
    selected_file_ids = request.session.get("selected_file_ids", [])
    selected_currencies = request.session.get("selected_currencies", [])

    files = UploadedFile.objects.all().order_by("-uploaded_at")

    qs = Transaction.objects.all()
    if selected_file_ids:
        qs = qs.filter(uploaded_file_id__in=selected_file_ids)

    # Get unique currencies for dropdown
    all_currencies = sorted(
        {t.currency for t in Transaction.objects.all() if t.currency}
    )

    # Apply time filter (takes precedence over manual date range)
    time_filter = request.GET.get("time_filter", "all")
    custom_start = request.GET.get("start_date") if time_filter == "custom" else None
    custom_end = request.GET.get("end_date") if time_filter == "custom" else None

    # Helper function to parse date strings
    def parse_date(date_str):
        if not date_str:
            return None
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.datetime.strptime(date_str, fmt).date()
            except Exception:
                continue
        return None

    # Get all transactions first
    all_transactions = list(qs)

    # Filter by time period
    filtered_transactions = []
    today = datetime.date.today()

    for t in all_transactions:
        transaction_date = parse_date(t.date)
        if not transaction_date:
            continue

        include = False

        if time_filter == "all":
            include = True
        elif time_filter == "last_year":
            one_year_ago = today - datetime.timedelta(days=365)
            include = transaction_date >= one_year_ago
        elif time_filter == "custom" and custom_start and custom_end:
            start_dt = parse_date(custom_start)
            end_dt = parse_date(custom_end)
            if start_dt and end_dt:
                include = start_dt <= transaction_date <= end_dt

        if include:
            filtered_transactions.append(t)

    # Filter by currencies if selected in session
    if selected_currencies:
        filtered_transactions = [
            t for t in filtered_transactions if t.currency in selected_currencies
        ]

    # Filter out excluded categories
    excluded_categories = get_excluded_categories()
    filtered_transactions = filter_transactions_by_excluded_categories(
        filtered_transactions, excluded_categories
    )

    transactions_qs = filtered_transactions
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
            "start_date": custom_start.strftime("%Y-%m-%d") if custom_start else "",
            "end_date": custom_end.strftime("%Y-%m-%d") if custom_end else "",
            "filtered_category_totals": filtered_category_totals,
            "filtered_category_totals_json": json.dumps(filtered_category_totals),
            "all_currencies": all_currencies,
            "selected_currencies": selected_currencies,
        },
    )


def monthly_budget(request):
    """Monthly budget view showing spending by category with historical averages"""
    import datetime
    from collections import defaultdict

    from .models import Transaction, UploadedFile

    # Get filters from session
    selected_file_ids = request.session.get("selected_file_ids", [])
    selected_currencies = request.session.get("selected_currencies", [])

    files = UploadedFile.objects.all().order_by("-uploaded_at")

    # Get all transactions
    qs = Transaction.objects.all()
    if selected_file_ids:
        qs = qs.filter(uploaded_file_id__in=selected_file_ids)

    all_transactions = list(qs)

    # Get unique currencies for dropdown
    all_currencies = sorted(
        {t.currency for t in Transaction.objects.all() if t.currency}
    )

    # Helper function to parse date strings
    def parse_date(date_str):
        if not date_str:
            return None
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.datetime.strptime(date_str, fmt).date()
            except Exception:
                continue
        return None

    # Filter by currencies if selected in session
    if selected_currencies:
        all_transactions = [
            t for t in all_transactions if t.currency in selected_currencies
        ]

    # Filter out excluded categories
    excluded_categories = get_excluded_categories()
    all_transactions = filter_transactions_by_excluded_categories(
        all_transactions, excluded_categories
    )

    # Determine primary currency (most common in filtered transactions)
    currency_counts = defaultdict(int)
    for t in all_transactions:
        if t.currency:
            currency_counts[t.currency] += 1
    primary_currency = max(currency_counts, default="CHF") if currency_counts else "CHF"

    # Group transactions by month and category
    monthly_by_category = defaultdict(lambda: defaultdict(float))

    for t in all_transactions:
        if not t.amount or t.amount > 0 or not t.category or t.category == "Uncounted":
            continue  # Skip income and uncategorized

        transaction_date = parse_date(t.date)
        if not transaction_date:
            continue

        month_key = transaction_date.strftime("%Y-%m")
        monthly_by_category[month_key][t.category] += abs(t.amount)

    # Calculate statistics for each category
    category_stats = defaultdict(
        lambda: {
            "months": [],
            "amounts": [],
            "total": 0.0,
            "average": 0.0,
            "min": float("inf"),
            "max": 0.0,
            "count": 0,
        }
    )

    for month_key in sorted(monthly_by_category.keys()):
        for category, amount in monthly_by_category[month_key].items():
            category_stats[category]["months"].append(month_key)
            category_stats[category]["amounts"].append(amount)
            category_stats[category]["total"] += amount
            category_stats[category]["min"] = min(
                category_stats[category]["min"], amount
            )
            category_stats[category]["max"] = max(
                category_stats[category]["max"], amount
            )
            category_stats[category]["count"] += 1

    # Calculate averages
    for category in category_stats:
        if category_stats[category]["count"] > 0:
            category_stats[category]["average"] = (
                category_stats[category]["total"] / category_stats[category]["count"]
            )
        if category_stats[category]["min"] == float("inf"):
            category_stats[category]["min"] = 0

    # Get current month and previous month
    today = datetime.date.today()
    current_month = today.strftime("%Y-%m")
    current_month_spending = monthly_by_category.get(current_month, {})

    # Calculate previous month
    first_day_current = datetime.date(today.year, today.month, 1)
    last_day_previous = first_day_current - datetime.timedelta(days=1)
    previous_month = last_day_previous.strftime("%Y-%m")
    previous_month_spending = monthly_by_category.get(previous_month, {})

    # Prepare data for chart - show last 12 months
    all_months = sorted(
        set(
            month
            for months in [stats["months"] for stats in category_stats.values()]
            for month in months
        )
    )

    if len(all_months) == 0:
        all_months = [current_month]

    # Prepare chart data - ALL categories sorted by average spending
    all_categories = sorted(
        [(cat, stats["average"]) for cat, stats in category_stats.items()],
        key=lambda x: x[1],
        reverse=True,
    )

    category_labels = [cat[0] for cat in all_categories]
    category_averages = [cat[1] for cat in all_categories]

    chart_data = {
        "labels": category_labels,
        "averages": category_averages,
    }

    # Calculate totals for the overview
    current_month_total = sum(current_month_spending.values())

    # Calculate average spending per month (total of all months / number of months)
    total_all_months = sum(
        sum(monthly_by_category[month].values()) for month in monthly_by_category.keys()
    )
    num_months = len(monthly_by_category) if monthly_by_category else 1
    average_spending = total_all_months / num_months if num_months > 0 else 0

    # Prepare category rows with pre-calculated comparison values for BOTH current and previous month
    category_rows = []
    for category, stats in sorted(
        category_stats.items(), key=lambda x: x[1]["average"], reverse=True
    ):
        current_amount = current_month_spending.get(category, 0)
        previous_amount = previous_month_spending.get(category, 0)

        is_current_over_budget = (
            current_amount > stats["average"] if stats["average"] > 0 else False
        )
        is_previous_over_budget = (
            previous_amount > stats["average"] if stats["average"] > 0 else False
        )

        current_difference = (
            abs(current_amount - stats["average"]) if current_amount > 0 else 0
        )
        previous_difference = (
            abs(previous_amount - stats["average"]) if previous_amount > 0 else 0
        )

        category_rows.append(
            {
                "category": category,
                "current_amount": current_amount,
                "previous_amount": previous_amount,
                "average": stats["average"],
                "min": stats["min"],
                "max": stats["max"],
                "count": stats["count"],
                "is_current_over_budget": is_current_over_budget,
                "is_previous_over_budget": is_previous_over_budget,
                "current_difference": current_difference,
                "previous_difference": previous_difference,
            }
        )

    import json

    return render(
        request,
        "dashboard/monthly_budget.html",
        {
            "current_month": current_month,
            "previous_month": previous_month,
            "current_month_total": current_month_total,
            "previous_month_total": sum(previous_month_spending.values()),
            "average_spending": average_spending,
            "all_months": all_months,
            "category_stats": dict(
                sorted(
                    category_stats.items(), key=lambda x: x[1]["average"], reverse=True
                )
            ),
            "category_rows": category_rows,
            "current_month_spending": dict(
                sorted(current_month_spending.items(), key=lambda x: x[1], reverse=True)
            ),
            "previous_month_spending": dict(
                sorted(
                    previous_month_spending.items(), key=lambda x: x[1], reverse=True
                )
            ),
            "chart_data": json.dumps(chart_data),
            "files": files,
            "selected_file_ids": selected_file_ids,
            "all_currencies": all_currencies,
            "selected_currencies": selected_currencies,
            "primary_currency": primary_currency,
        },
    )


import pandas as pd
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt


def dashboard(request):
    import datetime
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

    # Apply time filter (from session storage via query params or default to all)
    time_filter = request.GET.get("time_filter", "all")
    custom_start = request.GET.get("start_date")
    custom_end = request.GET.get("end_date")

    # Helper function to parse date strings
    def parse_date(date_str):
        if not date_str:
            return None
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.datetime.strptime(date_str, fmt).date()
            except Exception:
                continue
        return None

    # Filter by time period
    filtered_transactions = []
    today = datetime.date.today()

    for t in all_transactions:
        transaction_date = parse_date(t.date)
        if not transaction_date:
            continue

        include = False

        if time_filter == "all":
            include = True
        elif time_filter == "last_year":
            one_year_ago = today - datetime.timedelta(days=365)
            include = transaction_date >= one_year_ago
        elif time_filter == "custom" and custom_start and custom_end:
            start_date = parse_date(custom_start)
            end_date = parse_date(custom_end)
            if start_date and end_date:
                include = start_date <= transaction_date <= end_date

        if include:
            filtered_transactions.append(t)

    all_transactions = filtered_transactions

    # Filter out excluded categories
    excluded_categories = get_excluded_categories()
    all_transactions = filter_transactions_by_excluded_categories(
        all_transactions, excluded_categories
    )

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
            {
                "category": category,
                "total": total,
                "currencies": dict(currency_amounts),
            }
        )

    # Sort by total and get top 5, then assign colors in order
    top_spending = sorted(top_spending, key=lambda x: x["total"], reverse=True)[:5]

    # Assign colors AFTER sorting to ensure consistency
    spending_colors = [
        "#ef4444",
        "#f97316",
        "#f59e0b",
        "#eab308",
        "#84cc16",
        "#22c55e",
        "#10b981",
        "#14b8a6",
        "#06b6d4",
        "#0ea5e9",
    ]
    for idx, item in enumerate(top_spending):
        item["color"] = spending_colors[idx % len(spending_colors)]

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
            {
                "category": category,
                "total": total,
                "currencies": dict(currency_amounts),
            }
        )

    # Sort by total and get top 5, then assign colors in order
    top_income = sorted(top_income, key=lambda x: x["total"], reverse=True)[:5]

    # Assign colors AFTER sorting to ensure consistency
    income_colors = [
        "#22c55e",
        "#10b981",
        "#14b8a6",
        "#06b6d4",
        "#0ea5e9",
        "#3b82f6",
        "#6366f1",
        "#8b5cf6",
        "#a855f7",
        "#d946ef",
    ]
    for idx, item in enumerate(top_income):
        item["color"] = income_colors[
            idx % len(income_colors)
        ]  # Sort by total and get top 5
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

    # Calculate monthly expenses vs income data
    monthly_data = defaultdict(lambda: {"expenses": 0.0, "income": 0.0})
    for t in all_transactions:
        transaction_date = parse_date(t.date)
        if not transaction_date:
            continue
        month_key = transaction_date.strftime("%Y-%m")
        if t.amount and t.amount < 0:
            monthly_data[month_key]["expenses"] += abs(t.amount)
        elif t.amount and t.amount > 0:
            monthly_data[month_key]["income"] += t.amount

    sorted_months = sorted(monthly_data.keys())
    monthly_labels = sorted_months
    monthly_expenses = [monthly_data[month]["expenses"] for month in sorted_months]
    monthly_income = [monthly_data[month]["income"] for month in sorted_months]

    monthly_chart_data = {
        "labels": monthly_labels,
        "expenses": monthly_expenses,
        "income": monthly_income,
    }

    return render(
        request,
        "transactions/dashboard.html",
        {
            "transactions": transactions,
            "top_spending": top_spending,
            "top_income": top_income,
            "top_spending_json": json.dumps(top_spending),
            "top_income_json": json.dumps(top_income),
            "monthly_chart_data": json.dumps(monthly_chart_data),
        },
    )


import json


def delete_file(request, file_id):
    """Delete an uploaded file and all its associated transactions"""
    from django.http import JsonResponse
    from django.shortcuts import redirect

    from .models import UploadedFile

    if request.method == "POST":
        try:
            uploaded_file = UploadedFile.objects.get(id=file_id)
            uploaded_file.delete()  # This will cascade delete all related transactions

            # If it's an AJAX request, return JSON
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"success": True, "message": "File deleted successfully"}
                )
        except UploadedFile.DoesNotExist:
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse(
                    {"success": False, "error": "File not found"}, status=404
                )

    # Redirect back to the referrer or dashboard for non-AJAX requests
    return redirect(request.META.get("HTTP_REFERER", "/"))


# API Endpoints for Category Management
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods


def api_get_transactions(request):
    """API endpoint to get all transactions with their details"""
    from .models import Transaction

    # Get filters from session
    selected_file_ids = request.session.get("selected_file_ids", [])
    selected_currencies = request.session.get("selected_currencies", [])

    # Filter transactions based on session settings
    qs = Transaction.objects.all().order_by("-date", "-id")

    if selected_file_ids:
        qs = qs.filter(uploaded_file_id__in=selected_file_ids)
    if selected_currencies:
        qs = qs.filter(currency__in=selected_currencies)

    transactions = [
        {
            "id": t.id,
            "date": t.date,
            "booking_text": t.booking_text,
            "category": t.category if t.category else "Uncounted",
            "amount": float(t.amount) if t.amount else 0.0,
            "currency": t.currency if t.currency else "",
        }
        for t in qs[:500]  # Limit to 500 most recent transactions
    ]

    # Get all unique categories
    all_categories = sorted(
        set(t["category"] for t in transactions if t["category"] != "Uncounted")
    )

    return JsonResponse(
        {"transactions": transactions, "all_categories": all_categories}
    )


@csrf_exempt
@require_http_methods(["POST"])
def api_update_category(request, transaction_id):
    """API endpoint to update a transaction's category"""
    import json

    from .models import Transaction

    try:
        data = json.loads(request.body)
        new_category = data.get("category", "")

        # Use categorization service to record manual categorization
        try:
            from .categorization_service import TransactionCategorizationService

            categorization_service = TransactionCategorizationService()

            success = categorization_service.record_manual_categorization(
                transaction_id, new_category
            )

            if success:
                return JsonResponse({"success": True, "category": new_category})
            else:
                return JsonResponse(
                    {"success": False, "error": "Transaction not found"}, status=404
                )

        except Exception:
            # Fallback to original method if categorization service fails
            transaction = Transaction.objects.get(id=transaction_id)
            transaction.category = new_category
            transaction.is_manually_categorized = True
            transaction.category_confidence = 1.0
            transaction.save()

            return JsonResponse({"success": True, "category": new_category})

    except Transaction.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Transaction not found"}, status=404
        )
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


@require_http_methods(["POST"])
def api_create_category(request):
    """API endpoint to create a new category"""
    import json

    try:
        data = json.loads(request.body)
        category_name = data.get("name", "").strip()

        if not category_name:
            return JsonResponse(
                {"success": False, "error": "Category name is required"}, status=400
            )

        # Check if category already exists (case-insensitive)
        from .models import Transaction

        existing_categories = set(
            t.category.lower()
            for t in Transaction.objects.all()
            if t.category and t.category != "Uncounted"
        )

        if category_name.lower() in existing_categories:
            return JsonResponse(
                {
                    "success": False,
                    "error": f"Category '{category_name}' already exists",
                },
                status=400,
            )

        # Category will be available for use in transaction dropdowns
        # We don't need to store it separately - it's stored when assigned to transactions
        return JsonResponse({"success": True, "category": category_name})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)


def expenses_by_category_data_ajax(request):
    """AJAX endpoint for expenses by category time filtering"""
    import datetime
    from collections import defaultdict

    from .models import Transaction, UploadedFile

    try:
        # Get time filter parameters
        time_filter = request.GET.get("time_filter", "all")
        custom_start = None
        custom_end = None

        # Parse date helper function
        def parse_date(date_str):
            if not date_str:
                return None
            for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
                try:
                    return datetime.datetime.strptime(date_str, fmt).date()
                except Exception:
                    continue
            return None

        # Handle time filtering
        if time_filter == "custom":
            start_date_str = request.GET.get("start_date")
            end_date_str = request.GET.get("end_date")
            custom_start = parse_date(start_date_str)
            custom_end = parse_date(end_date_str)
        elif time_filter == "last_year":
            today = datetime.date.today()
            custom_start = today - datetime.timedelta(days=365)
            custom_end = today
        # 'all' time means no filtering

        # Get all transactions
        transactions = list(Transaction.objects.all().values())

        # Apply time filtering
        if custom_start and custom_end:
            filtered_transactions = []
            for t in transactions:
                t_date = parse_date(t["date"])
                if t_date and custom_start <= t_date <= custom_end:
                    filtered_transactions.append(t)
            transactions = filtered_transactions

        # Filter out excluded categories
        excluded_categories = get_excluded_categories()
        transactions = [
            t for t in transactions if t.get("category") not in excluded_categories
        ]

        # Filter for expenses (negative amounts)
        expense_transactions = [t for t in transactions if t["amount"] < 0]

        # Group by category
        category_totals = defaultdict(float)
        for t in expense_transactions:
            if t["category"] and t["category"] != "Uncounted":
                category_totals[t["category"]] += abs(t["amount"])

        # Sort and get top categories
        sorted_categories = sorted(
            category_totals.items(), key=lambda x: x[1], reverse=True
        )

        # Prepare chart data
        labels = [cat[0] for cat in sorted_categories]
        amounts = [cat[1] for cat in sorted_categories]

        return JsonResponse(
            {"success": True, "chart_data": {"labels": labels, "amounts": amounts}}
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


def expenses_vs_income_data_ajax(request):
    """AJAX endpoint for expenses vs income time filtering"""
    import datetime
    from collections import defaultdict

    from .models import Transaction, UploadedFile

    try:
        # Get time filter parameters
        time_filter = request.GET.get("time_filter", "all")
        custom_start = None
        custom_end = None

        # Parse date helper function
        def parse_date(date_str):
            if not date_str:
                return None
            for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
                try:
                    return datetime.datetime.strptime(date_str, fmt).date()
                except Exception:
                    continue
            return None

        # Handle time filtering
        if time_filter == "custom":
            start_date_str = request.GET.get("start_date")
            end_date_str = request.GET.get("end_date")
            custom_start = parse_date(start_date_str)
            custom_end = parse_date(end_date_str)
        elif time_filter == "last_year":
            today = datetime.date.today()
            custom_start = today - datetime.timedelta(days=365)
            custom_end = today

        # Get all transactions
        transactions = list(Transaction.objects.all().values())

        # Apply time filtering
        if custom_start and custom_end:
            filtered_transactions = []
            for t in transactions:
                t_date = parse_date(t["date"])
                if t_date and custom_start <= t_date <= custom_end:
                    filtered_transactions.append(t)
            transactions = filtered_transactions

        # Simple monthly aggregation for now
        monthly_data = defaultdict(lambda: {"expenses": 0, "income": 0})

        for t in transactions:
            t_date = parse_date(t["date"])
            if t_date:
                month_key = f"{t_date.year}-{t_date.month:02d}"
                if t["amount"] < 0:
                    monthly_data[month_key]["expenses"] += abs(t["amount"])
                else:
                    monthly_data[month_key]["income"] += t["amount"]

        # Sort by month and prepare chart data
        sorted_months = sorted(monthly_data.keys())
        labels = sorted_months
        expenses = [monthly_data[month]["expenses"] for month in sorted_months]
        income = [monthly_data[month]["income"] for month in sorted_months]

        return JsonResponse(
            {
                "success": True,
                "chart_data": {
                    "labels": labels,
                    "expenses": expenses,
                    "income": income,
                },
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


def income_by_category_data_ajax(request):
    """AJAX endpoint for income by category time filtering"""
    import datetime
    from collections import defaultdict

    from .models import Transaction, UploadedFile

    try:
        # Get time filter parameters
        time_filter = request.GET.get("time_filter", "all")
        custom_start = None
        custom_end = None

        # Parse date helper function
        def parse_date(date_str):
            if not date_str:
                return None
            for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
                try:
                    return datetime.datetime.strptime(date_str, fmt).date()
                except Exception:
                    continue
            return None

        # Handle time filtering
        if time_filter == "custom":
            start_date_str = request.GET.get("start_date")
            end_date_str = request.GET.get("end_date")
            custom_start = parse_date(start_date_str)
            custom_end = parse_date(end_date_str)
        elif time_filter == "last_year":
            today = datetime.date.today()
            custom_start = today - datetime.timedelta(days=365)
            custom_end = today

        # Get all transactions
        transactions = list(Transaction.objects.all().values())

        # Apply time filtering
        if custom_start and custom_end:
            filtered_transactions = []
            for t in transactions:
                t_date = parse_date(t["date"])
                if t_date and custom_start <= t_date <= custom_end:
                    filtered_transactions.append(t)
            transactions = filtered_transactions

        # Filter out excluded categories
        excluded_categories = get_excluded_categories()
        transactions = [
            t for t in transactions if t.get("category") not in excluded_categories
        ]

        # Filter for income (positive amounts)
        income_transactions = [t for t in transactions if t["amount"] > 0]

        # Group by category
        category_totals = defaultdict(float)
        for t in income_transactions:
            if t["category"] and t["category"] != "Uncounted":
                category_totals[t["category"]] += t["amount"]

        # Sort and get top categories
        sorted_categories = sorted(
            category_totals.items(), key=lambda x: x[1], reverse=True
        )

        # Prepare chart data
        labels = [cat[0] for cat in sorted_categories]
        amounts = [cat[1] for cat in sorted_categories]

        return JsonResponse(
            {"success": True, "chart_data": {"labels": labels, "amounts": amounts}}
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


def dashboard_data_ajax(request):
    """AJAX endpoint for dynamic time filtering on dashboard"""
    import datetime
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

    # Apply time filter
    time_filter = request.GET.get("time_filter", "all")
    custom_start = request.GET.get("start_date")
    custom_end = request.GET.get("end_date")

    # Helper function to parse date strings
    def parse_date(date_str):
        if not date_str:
            return None
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
            try:
                return datetime.datetime.strptime(date_str, fmt).date()
            except Exception:
                continue
        return None

    # Filter by time period
    filtered_transactions = []
    today = datetime.date.today()

    for t in all_transactions:
        transaction_date = parse_date(t.date)
        if not transaction_date:
            continue

        include = False

        if time_filter == "all":
            include = True
        elif time_filter == "last_year":
            one_year_ago = today - datetime.timedelta(days=365)
            include = transaction_date >= one_year_ago
        elif time_filter == "custom" and custom_start and custom_end:
            start_date = parse_date(custom_start)
            end_date = parse_date(custom_end)
            if start_date and end_date:
                include = start_date <= transaction_date <= end_date

        if include:
            filtered_transactions.append(t)

    all_transactions = filtered_transactions

    # Calculate top spending categories (negative amounts) with currency breakdown
    expense_by_category_currency = defaultdict(lambda: defaultdict(float))
    for t in all_transactions:
        if t.amount and t.amount < 0 and t.category and t.category != "Uncounted":
            currency = t.currency if t.currency else "Unknown"
            expense_by_category_currency[t.category][currency] += abs(t.amount)

    # Convert to list with total and currency breakdown for spending
    top_spending = []
    colors = [
        "#FF6B6B",
        "#4ECDC4",
        "#45B7D1",
        "#96CEB4",
        "#FECA57",
        "#FF9FF3",
        "#54A0FF",
        "#5F27CD",
        "#00D2D3",
        "#FF9F43",
        "#10AC84",
        "#EE5A24",
        "#0984E3",
        "#A29BFE",
        "#FD79A8",
    ]

    for i, (category, currencies) in enumerate(expense_by_category_currency.items()):
        total = sum(currencies.values())
        color = colors[i % len(colors)]
        top_spending.append(
            {
                "category": category,
                "total": total,
                "color": color,
                "currencies": dict(currencies),
            }
        )

    # Sort by total descending and take top 10
    top_spending.sort(key=lambda x: x["total"], reverse=True)
    top_spending = top_spending[:10]

    # Calculate top income categories (positive amounts) with currency breakdown
    income_by_category_currency = defaultdict(lambda: defaultdict(float))
    for t in all_transactions:
        if t.amount and t.amount > 0 and t.category and t.category != "Uncounted":
            currency = t.currency if t.currency else "Unknown"
            income_by_category_currency[t.category][currency] += t.amount

    # Convert to list with total and currency breakdown for income
    top_income = []

    for i, (category, currencies) in enumerate(income_by_category_currency.items()):
        total = sum(currencies.values())
        color = colors[i % len(colors)]
        top_income.append(
            {
                "category": category,
                "total": total,
                "color": color,
                "currencies": dict(currencies),
            }
        )

    # Sort by total descending and take top 10
    top_income.sort(key=lambda x: x["total"], reverse=True)
    top_income = top_income[:10]

    return JsonResponse(
        {
            "success": True,
            "top_spending": top_spending,
            "top_income": top_income,
            "time_filter": time_filter,
            "custom_start": custom_start,
            "custom_end": custom_end,
        }
    )


# Semantic Categorization API Endpoints


@csrf_exempt
@require_http_methods(["GET"])
def api_categorization_stats(request):
    """API endpoint to get categorization statistics"""
    try:
        from .categorization_service import TransactionCategorizationService

        categorization_service = TransactionCategorizationService()

        stats = categorization_service.get_categorization_stats()
        return JsonResponse({"success": True, "stats": stats})

    except Exception as e:
        import sys
        import traceback

        error_msg = f"{str(e)}\n{traceback.format_exc()}"
        print(f"Error in api_categorization_stats: {error_msg}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return JsonResponse(
            {"success": False, "error": str(e), "details": error_msg}, status=500
        )


@csrf_exempt
@require_http_methods(["POST"])
def api_recategorize_uncategorized(request):
    """API endpoint to re-run categorization on uncategorized transactions"""
    try:
        from .categorization_service import TransactionCategorizationService

        categorization_service = TransactionCategorizationService()

        stats = categorization_service.recategorize_uncategorized_transactions()
        # Return stats directly with the expected keys
        return JsonResponse(
            {
                "success": True,
                "total": stats.get("total", 0),
                "categorized": stats.get("categorized", 0),
                "high_confidence": stats.get("high_confidence", 0),
                "medium_confidence": stats.get("medium_confidence", 0),
                "low_confidence": stats.get("low_confidence", 0),
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


def dashboard_monthly_data_ajax(request):
    """AJAX endpoint for monthly expenses vs income data on dashboard"""
    import datetime
    from collections import defaultdict

    from .models import Transaction

    try:
        # Get time filter parameters
        time_filter = request.GET.get("time_filter", "all")
        custom_start = None
        custom_end = None

        # Parse date helper function
        def parse_date(date_str):
            if not date_str:
                return None
            for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
                try:
                    return datetime.datetime.strptime(date_str, fmt).date()
                except Exception:
                    continue
            return None

        # Handle time filtering
        if time_filter == "custom":
            start_date_str = request.GET.get("start_date")
            end_date_str = request.GET.get("end_date")
            custom_start = parse_date(start_date_str)
            custom_end = parse_date(end_date_str)
        elif time_filter == "last_year":
            today = datetime.date.today()
            custom_start = today - datetime.timedelta(days=365)
            custom_end = today
        else:
            # 'all' time means no filtering
            pass

        # Get all transactions
        transactions = list(Transaction.objects.all().values())

        # Apply time filtering
        if custom_start and custom_end:
            filtered_transactions = []
            for t in transactions:
                t_date = parse_date(t["date"])
                if t_date and custom_start <= t_date <= custom_end:
                    filtered_transactions.append(t)
            transactions = filtered_transactions

        # Filter out excluded categories
        excluded_categories = get_excluded_categories()
        transactions = [
            t for t in transactions if t.get("category") not in excluded_categories
        ]

        # Group by month
        monthly_data = defaultdict(lambda: {"expenses": 0.0, "income": 0.0})

        for t in transactions:
            t_date = parse_date(t["date"])
            if not t_date:
                continue

            # Create month key (YYYY-MM)
            month_key = t_date.strftime("%Y-%m")

            if t["amount"] < 0:
                monthly_data[month_key]["expenses"] += abs(t["amount"])
            elif t["amount"] > 0:
                monthly_data[month_key]["income"] += t["amount"]

        # Sort by month and prepare for chart
        sorted_months = sorted(monthly_data.keys())
        labels = sorted_months
        expenses_data = [monthly_data[month]["expenses"] for month in sorted_months]
        income_data = [monthly_data[month]["income"] for month in sorted_months]

        return JsonResponse(
            {
                "success": True,
                "chart_data": {
                    "labels": labels,
                    "expenses": expenses_data,
                    "income": income_data,
                },
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})


@csrf_exempt
@require_http_methods(["GET"])
def api_low_confidence_transactions(request):
    """API endpoint to get transactions with low confidence predictions for review"""
    try:
        from .categorization_service import TransactionCategorizationService

        categorization_service = TransactionCategorizationService()

        confidence_threshold = float(request.GET.get("threshold", 0.6))
        transactions = categorization_service.improve_low_confidence_predictions(
            confidence_threshold
        )

        return JsonResponse({"success": True, "transactions": transactions})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_get_category_suggestions(request):
    """API endpoint to get category suggestions for a merchant"""
    import json

    try:
        from .categorization_service import TransactionCategorizationService

        categorization_service = TransactionCategorizationService()

        data = json.loads(request.body)
        merchant_text = data.get("merchant", "").strip()

        if not merchant_text:
            return JsonResponse(
                {"success": False, "error": "Merchant text is required"}, status=400
            )

        suggestions = categorization_service.get_suggestions_for_merchant(merchant_text)
        return JsonResponse({"success": True, "suggestions": suggestions})

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@require_http_methods(["POST"])
def api_update_excluded_categories(request):
    """API endpoint to update excluded categories"""
    import json

    try:
        from .models import DashboardSettings

        data = json.loads(request.body)
        excluded_categories = data.get("excluded_categories", [])

        # Validate that all items are strings
        if not isinstance(excluded_categories, list):
            return JsonResponse(
                {"success": False, "error": "excluded_categories must be a list"},
                status=400,
            )

        excluded_categories = [str(cat).strip() for cat in excluded_categories]

        # Update or create dashboard settings
        settings = DashboardSettings.get_settings()
        settings.excluded_categories = excluded_categories
        settings.save()

        return JsonResponse(
            {
                "success": True,
                "message": "Excluded categories updated successfully",
                "excluded_categories": excluded_categories,
            }
        )

    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def api_budget_comparison(request):
    """API endpoint to get budget data for a specific month"""
    import json
    from collections import defaultdict
    from datetime import datetime

    from django.utils.dateparse import parse_date as django_parse_date

    try:
        year = request.GET.get("year")
        month = request.GET.get("month")

        if not year or not month:
            return JsonResponse(
                {"success": False, "error": "Year and month parameters required"},
                status=400,
            )

        year = int(year)
        month = int(month)

        # Get all transactions
        transactions = Transaction.objects.all()

        # Helper function to parse dates
        def parse_date(date_str):
            for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
                try:
                    return datetime.strptime(date_str, fmt).date()
                except:
                    continue
            return None

        # Filter transactions for the selected month
        month_transactions = []
        for t in transactions:
            date_obj = parse_date(t.date)
            if date_obj and date_obj.year == year and date_obj.month == month:
                if t.amount < 0:  # Only negative (spending)
                    month_transactions.append(t)

        # Calculate month total
        month_total = sum(abs(t.amount) for t in month_transactions)

        # Group by category
        category_totals = defaultdict(float)
        for t in month_transactions:
            category_totals[t.category or "Uncategorized"] += abs(t.amount)

        # Calculate average spending across all months (excluding the selected month)
        all_transactions = transactions.filter(amount__lt=0)
        month_totals_by_month = defaultdict(float)
        month_count = defaultdict(int)

        for t in all_transactions:
            date_obj = parse_date(t.date)
            if date_obj:
                month_key = f"{date_obj.year}-{date_obj.month:02d}"
                month_totals_by_month[month_key] += abs(t.amount)
                month_count[month_key] += 1

        # Calculate average
        if month_totals_by_month:
            average_spending = sum(month_totals_by_month.values()) / len(
                month_totals_by_month
            )
        else:
            average_spending = 0

        # Prepare category rows
        category_rows = []
        for category, amount in sorted(
            category_totals.items(), key=lambda x: x[1], reverse=True
        ):
            category_rows.append(
                {
                    "category": category,
                    "month_amount": float(amount),
                    "average": average_spending / len(category_totals)
                    if category_totals
                    else 0,
                }
            )

        # Get primary currency
        primary_currency = "CHF"
        first_transaction = transactions.first()
        if first_transaction and first_transaction.currency:
            primary_currency = first_transaction.currency

        return JsonResponse(
            {
                "success": True,
                "month_total": month_total,
                "average_spending": average_spending,
                "category_rows": category_rows,
                "primary_currency": primary_currency,
            }
        )

    except Exception as e:
        import traceback

        traceback.print_exc()
        return JsonResponse({"success": False, "error": str(e)}, status=500)
