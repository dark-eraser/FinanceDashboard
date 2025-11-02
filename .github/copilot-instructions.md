# FinanceTracker Copilot Instructions

## Project Overview

FinanceTracker is a Django-based personal finance analytics application that processes and visualizes transactions from ZKB (Zürcher Kantonalbank) and Revolut bank statements. The project evolved from a Python script-based approach to a full Django web application.

## Architecture

### Django Application Structure

The active codebase is a Django web app in `faster/` with SQLite backend and Chart.js visualizations. **Note**: README references legacy `src/` directory and Streamlit dashboard - these are deprecated and not in active use.

### Django Structure (`faster/`)

- **`dashboard/`**: Main Django project (settings, root URLs)
- **`transactions/`**: Core app handling file uploads, transaction storage, and analytics views
- **`templates/`**: Two-level structure - `faster/templates/` (base.html) and `transactions/templates/` (dashboard views)
- **`db.sqlite3`**: SQLite database storing `UploadedFile` and `Transaction` models

## Data Model

### Transaction Model (`transactions/models.py`)

- Stores ALL fields as strings/floats (not proper DateField) - `date` is `CharField(max_length=32)`
- Linked to `UploadedFile` via ForeignKey for multi-file tracking
- Fields: `date`, `booking_text`, `category`, `amount` (float)

### CSV Format Support

The app handles multiple bank statement formats with **flexible, case-insensitive column matching**:

**ZKB Raw Format** (semicolon-separated): `Date;Booking text;Curr;Amount details;ZKB reference;Reference number;Debit CHF;Credit CHF;Value date;Balance CHF;Payment purpose;Details;Category`
**ZKB Normalized Format** (comma-separated): `Date,description,type,amount,currency,fee,reference,Category`

**Revolut Raw Format**: `Type,Product,Started Date,Completed Date,Description,Amount,Fee,Currency,State,Balance,Category`
**Revolut Normalized Format**: `value_date,description,type,amount,currency,fee,reference,Category`

**Critical**: CSV parsing in `views.dashboard()` tries multiple separators (`;`, `,`) and auto-detection with pandas `sep=None`. Column names are normalized to lowercase with `.strip()` for matching. The parser maps different column name variations to standardized fields: `Date`, `Booking_text`, `Category`, `Amount`.

## Key Workflows

### Running the Django App

```bash
cd faster
python manage.py runserver
```

**Note**: Django project is in `faster/` subdirectory, not root. Always `cd faster` first.

### Database Migrations

```bash
cd faster
python manage.py makemigrations
python manage.py migrate
```

Existing migration: `0001_initial.py` creates `Transaction` and `UploadedFile` tables.

### CSV Upload Flow

1. User uploads CSV via dashboard form (`transactions/dashboard.html`)
2. `dashboard()` view detects format, normalizes columns to `Date`, `Booking_text`, `Category`, `Amount`
3. Creates `UploadedFile` record, then bulk-creates `Transaction` objects
4. Displays transactions in table

## Code Patterns

### Date Handling Pattern

**IMPORTANT**: Dates are stored as `CharField` (not `DateField`) to handle multiple input formats from different banks. Use Python-side parsing for date filtering:

```python
def parse_date(date_str):
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(date_str, fmt).date()
        except Exception:
            continue
    return None
```

This pattern appears in `expenses_vs_income()` and other views. **Do not use Django ORM date filtering** (e.g., `.filter(date__gte=...)`) - it won't work on CharField fields.

### Visualization Pattern

All charts use Chart.js with data serialized via `json.dumps()` in views:

```python
chart_data = {"labels": [...], "amounts": [...]}
context = {"chart_data": json.dumps(chart_data)}
```

Templates parse with: `JSON.parse('{{ chart_data|safe|escapejs }}')`

### Category Aggregation Pattern

Use `defaultdict(float)` for category totals:

```python
from collections import defaultdict
category_totals = defaultdict(float)
for t in transactions:
    category_totals[t.category] += t.amount
```

**Filter out "Uncounted"** category in templates for cleaner visualizations.

## Dependencies

### Installation

```bash
pip install -r requirements.txt
pip install django django-htmx  # Not in requirements.txt, install separately
```

**Key packages**: pandas (CSV parsing), matplotlib/seaborn (visualization), Chart.js (frontend charts via CDN)

**Note**: Django and django-htmx are managed separately from `requirements.txt`. Always install them manually after installing requirements.

## Configuration Notes

- **Hardcoded Template Path**: `settings.py` has absolute path `/Users/darkeraser/Documents/dev/FinanceTracker/faster/templates` - should use `BASE_DIR / "templates"`
- **Debug Mode**: `DEBUG = True` and exposed `SECRET_KEY` in settings - not production-ready
- **No Static Files Setup**: No `STATIC_ROOT` or `collectstatic` configured

## Common Pitfalls

1. **Don't run Django commands from root** - `cd faster` first
2. **CSV separator issues** - Always test both `;` and `,` separators
3. **Date filtering requires Python-side logic** - ORM `.filter(date__gte=...)` won't work due to CharField storage
4. **Template inheritance** - `base.html` exists in both `faster/templates/` (used) and `transactions/templates/` (unused duplicate)

## File Locations

- **Pre-categorized CSVs**: `config/categorized_*.csv` (reference data with existing categorizations)
- **Normalized CSVs**: `data/normalized_*.csv` (processed exports, not used by Django app)
- **Raw uploads**: Stored in DB only (no file persistence after upload)
