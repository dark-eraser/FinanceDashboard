# FinanceTracker

A Python application for tracking and analyzing personal finances.

## Setup

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Installation

1. Clone or navigate to the project directory:
   ```bash
   cd /Users/darkeraser/Documents/dev/FinanceTracker
   ```

2. Create and activate a virtual environment:
   ```bash
   # Create virtual environment
   python3 -m venv venv

   # Activate virtual environment
   source venv/bin/activate  # On macOS/Linux
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Development Setup

For development work, make sure to activate the virtual environment before running any Python commands:

```bash
source venv/bin/activate
```

To deactivate the virtual environment when done:
```bash
deactivate
```

## Project Structure

```
FinanceTracker/
├── src/                 # Source code
├── data/               # Data files (ignored by git)
├── tests/              # Unit tests
├── config/             # Configuration files
├── requirements.txt    # Python dependencies
├── .gitignore         # Git ignore rules
└── README.md          # This file
```

## Features

- [ ] Transaction tracking
- [ ] Expense categorization
- [ ] Budget management
- [ ] Financial reporting
- [ ] Data visualization

## Usage

(Add usage instructions as you develop the application)

## Development

### Running Tests
```bash
pytest
```

### Code Formatting
```bash
black .
```

### Linting
```bash
flake8 .
```

## License

(Add your license information here)
