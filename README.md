# AI-Powered Retail Market Intelligence & Sales Optimisation

A Python project scaffold for retail market analysis, sales optimisation, and
machine-learning workflows, with MySQL for data storage and Power BI for
reporting. No datasets, trained models, or analysis pipeline are included yet.

## Technology

- Python 3
- MySQL
- pandas, NumPy, and scikit-learn
- Jupyter notebooks
- Power BI
- Git and GitHub

## Project structure

```text
.
├── config/                 # Local and project configuration
├── dashboard/powerbi/      # Power BI report files
├── data/
│   ├── external/           # Third-party source data (kept out of Git)
│   ├── processed/          # Derived datasets (kept out of Git)
│   └── raw/                # Source datasets (kept out of Git)
├── notebooks/              # Exploratory and development notebooks
├── reports/figures/        # Generated report figures
├── src/
│   ├── analysis/           # Analysis and metrics
│   ├── data/               # Data ingestion and transformation
│   ├── database/           # Database access
│   ├── models/             # Model implementations
│   ├── pipeline/           # End-to-end workflows
│   └── recommendations/    # Recommendation logic
├── tests/                  # Automated tests
├── main.py                 # Project entry point
├── requirements.txt        # Python dependencies
└── .env.example            # Environment-variable template
```

## Setup on Windows PowerShell

From the project directory, create and activate a virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If the Python launcher is unavailable, use `python -m venv .venv` instead.
Then install the dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Verify that Python is installed and available:

```powershell
py --version
python --version
python -c "import sys; print(sys.executable)"
```

Copy `.env.example` to `.env` and set local configuration values there. Do not
commit `.env` or put credentials in source files. The raw, processed, and
external data directories are intentionally excluded from Git; keep large or
sensitive data out of version control.

## Current status

This repository contains the initial project structure only. Add approved
retail data sources and implement the pipeline before running analyses. Running
`python main.py` confirms the scaffold is present; it does not perform analysis.
