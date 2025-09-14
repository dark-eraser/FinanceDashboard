# FinanceTracker

A Python application for tracking, categorizing, and visualizing personal finances from ZKB and Revolut statements.

## Setup

### Prerequisites

- Python 3.11 or higher
- pip package manager

### Installation

1. Clone or navigate to the project directory:

   ```bash
   cd /Users/darkeraser/Documents/dev/FinanceTracker
   ```

2. Create and activate a virtual environment:

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Download the required spaCy model:
   ```bash
   python -m spacy download en_core_web_sm
   ```

## Project Structure

```
FinanceTracker/
├── src/                 # Source code (parsers, categorization, utils)
├── data/                # Raw and processed CSVs
├── tests/               # Unit tests
├── config/              # Configuration files
├── requirements.txt     # Python dependencies
└── README.md            # This file
```

## Features

- Batch processing and categorization of all CSVs in `data/`
- Hybrid merchant categorization (mapping, keywords, Google Places API, user prompt)
- Robust date parsing and data cleaning
- Persistent merchant-category mapping
- Streamlit dashboard for interactive visualization

## Usage

1. (Optional) Batch categorize all CSVs:

   ```bash
   python src/categorize_all.py
   ```

2. Run the Streamlit dashboard:
   ```bash
   python -m streamlit run dashboard.py
   ```

## Development

- Run tests: `pytest`
- Format code: `black .`
- Lint code: `flake8 .`

## License

(Add your license information here)
