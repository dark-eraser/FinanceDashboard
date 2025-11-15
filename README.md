# FinanceTracker

A Django web application for tracking, categorizing, and visualizing personal finances from ZKB and Revolut bank statements.

## Features

- 📊 **Interactive Dashboard**: Web-based analytics with Chart.js visualizations
- 🏦 **Multi-Bank Support**: Handles both ZKB and Revolut statements automatically
- 🤖 **Auto-Categorization**: Smart categorization using merchant mapping and keyword matching
- 💰 **Expense Analytics**: Track spending by category, view income vs expenses, monthly trends
- 🔄 **Multi-line Transaction Support**: ZKB grouped transactions properly expanded
- 💾 **SQLite Backend**: Persistent storage with Django ORM

## Quick Start

### Prerequisites

- Python 3.11+ (tested with Python 3.13)
- pip package manager

### Installation

1. Clone and navigate to the project:

   ```bash
   cd /Users/darkeraser/Documents/dev/FinanceTracker
   ```

2. Create and activate a virtual environment:

   ```bash
   python3.13 -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   pip install django django-htmx  # Not in requirements.txt
   ```

4. Set up Django database:

   ```bash
   cd faster
   python manage.py migrate
   ```

5. Start the development server:

   ```bash
   python manage.py runserver
   ```

6. Open browser to: `http://localhost:8000/transactions/dashboard/`

## Project Structure

```
FinanceTracker/
├── faster/                          # Django web application
│   ├── manage.py                    # Django management
│   ├── dashboard/                   # Django project settings
│   ├── transactions/                # Main app (models, views, templates)
│   │   ├── models.py               # Transaction & UploadedFile models
│   │   ├── views.py                # Dashboard views & CSV upload
│   │   └── templates/              # HTML templates
│   ├── templates/base.html         # Base template
│   ├── db.sqlite3                  # SQLite database
│   └── helpers/                    # Preprocessing utilities
│       ├── preprocess_statement.py     # ⭐ Universal preprocessor (ZKB + Revolut)
│       ├── merchant_classifier.py      # Interactive categorization tool
│       ├── finance_utils.py            # Category keyword definitions
│       ├── google_places_helper.py     # Google Places API integration
│       ├── merchant_category_mapping.json  # 1335+ merchant mappings
│       └── README_PREPROCESSING.md     # Preprocessing documentation
├── data/                           # Processed CSV files
├── config/                         # Reference categorized statements
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

## Usage Workflow

### 1. Download Bank Statements

- **ZKB**: Download CSV from e-banking (semicolon-separated format)
- **Revolut**: Export statement from app (comma-separated format)

### 2. Preprocess Statements

The universal preprocessor handles both banks:

```bash
cd faster/helpers

# Auto-detect bank type and process
python3.13 preprocess_statement.py "~/Downloads/Account statement.csv"

# Force bank type if needed
python3.13 preprocess_statement.py input.csv --type zkb
python3.13 preprocess_statement.py input.csv --type revolut

# Custom output location
python3.13 preprocess_statement.py input.csv -o ../../data/zkb_2025_10.csv
```

**What preprocessing does:**

- ✅ Auto-detects bank (ZKB or Revolut)
- ✅ Expands ZKB multi-line transactions (removes parent summaries)
- ✅ Converts to normalized 8-column format
- ✅ Fixes vault transfer amounts (makes them negative)
- ✅ Auto-categorizes transactions
- ✅ Sorts by date (newest first)

Output: `preprocessed_<filename>.csv` ready for upload!

### 3. Upload to Dashboard

1. Make sure Django server is running:

   ```bash
   cd faster
   python manage.py runserver
   ```

2. Navigate to: `http://localhost:8000/transactions/dashboard/`

3. Click "Choose File" and upload the preprocessed CSV

4. View your transactions and analytics!

### 4. Improve Categorization (Optional)

If you have many "Uncounted" transactions:

```bash
cd faster/helpers
python3.13 merchant_classifier.py
```

This interactive tool will:

- Show you each unknown merchant with sample transactions (dates + amounts)
- Let you categorize them manually
- Optionally call Google Places API for suggestions
- Save mappings to `merchant_category_mapping.json`

Re-run preprocessing to apply new categories.

## Dashboard Features

### Available Views

1. **Dashboard** (`/transactions/dashboard/`)

   - Upload CSV files
   - View all transactions in table
   - Filter by date range

2. **Expenses by Category** (`/transactions/expenses-by-category/`)

   - Pie chart of spending by category
   - Excludes "Uncounted" for cleaner visualization
   - Date range filtering

3. **Expenses vs Income** (`/transactions/expenses-vs-income/`)

   - Bar chart comparing expenses (red) vs income (green)
   - Monthly breakdown
   - Net savings calculation

4. **Analytics** (`/transactions/analytics/`)
   - Combined analytics view
   - Multiple chart types
   - Category trends

## Data Format

### Input Formats

**ZKB** (12 columns, semicolon-separated):

```
Date;Booking text;Curr;Amount details;ZKB reference;Reference number;Debit CHF;Credit CHF;Value date;Balance CHF;Payment purpose;Details
```

**Revolut** (11 columns, comma-separated):

```
Type,Product,Started Date,Completed Date,Description,Amount,Fee,Currency,State,Balance,Category
```

### Normalized Output (8 columns, comma-separated):

```
value_date,description,type,amount,currency,fee,reference,Category
```

### Database Schema

**Transaction Model:**

- `value_date` (CharField) - Transaction date as string
- `description` (TextField) - Merchant/description
- `type` (CharField) - Transaction type
- `amount` (FloatField) - Amount (negative = expense, positive = income)
- `currency` (CharField) - Currency code (CHF, EUR, etc.)
- `fee` (FloatField) - Transaction fee
- `reference` (CharField) - Reference number
- `Category` (CharField) - Category (Groceries, Rent, etc.)
- `uploaded_file` (ForeignKey) - Link to source file

## Categories

Available categories (priority order):

1. **Refund** - Product returns, reimbursements
2. **Uncounted** - Default for unknown transactions
3. **Rent** - Monthly rent payments
4. **Vault** - Transfers to Revolut pockets
5. **Salary** - Income
6. **Groceries** - Supermarkets (Migros, Coop, Lidl, etc.)
7. **Dining** - Restaurants, cafes, food delivery
8. **Shopping** - Retail purchases
9. **Travel** - Transportation, hotels, flights
10. **Leisure** - Entertainment, hobbies
11. **Health** - Medical, pharmacy, insurance
12. **Utilities** - Bills, phone, internet
13. **Bank Transfer** - General transfers
14. **Car** - Fuel, parking, maintenance
15. **Subscriptions** - Recurring services

Categories are matched using:

1. Exact merchant match (from `merchant_category_mapping.json`)
2. Keyword matching (from `finance_utils.py`)
3. Defaults to "Uncounted"

## Troubleshooting

### Import Errors

If you see "Module not found":

```bash
pip install django django-htmx pandas matplotlib seaborn
```

### Django Server Won't Start

```bash
cd faster  # Make sure you're in the faster/ directory
python manage.py migrate
python manage.py runserver
```

### CSV Upload Fails

- Make sure file is preprocessed first with `preprocess_statement.py`
- Check file has 8 columns: `value_date,description,type,amount,currency,fee,reference,Category`
- Verify amounts are numbers (not strings)

### Charts Not Showing

- Check browser console for JavaScript errors
- Verify transactions have valid dates and amounts
- Try clearing browser cache

## Development

### Running Tests

```bash
cd faster
python manage.py test
```

### Making Database Changes

```bash
python manage.py makemigrations
python manage.py migrate
```

### Adding New Categories

Edit `faster/helpers/finance_utils.py`:

```python
CATEGORY_KEYWORDS = {
    "NewCategory": ["keyword1", "keyword2"],
    # ... other categories
}
```

## Configuration

### Template Paths

Update `faster/dashboard/settings.py` to use relative paths instead of hardcoded absolute paths.

### Debug Mode

For production, set in `settings.py`:

```python
DEBUG = False
SECRET_KEY = os.environ.get('SECRET_KEY')
```

## Google Places API (Optional)

For enhanced merchant categorization:

1. Get Google Places API key
2. Save to `creds.json`:

   ```json
   {
     "google_places_api_key": "your-api-key-here"
   }
   ```

3. Use in merchant classifier when prompted

## License

MIT License (or specify your license)
