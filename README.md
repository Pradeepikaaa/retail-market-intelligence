# retail-market-intelligence

## AI-Powered Retail Market Intelligence & Sales Optimisation

A Python project scaffold for retail market analysis, sales optimisation, and
machine-learning workflows, with MySQL for data storage and Power BI for
reporting. The repository includes a configurable data preprocessing pipeline;
raw datasets and trained models are kept out of version control.

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

## Phase 2: data preprocessing

Extract supported CSV, XLS, and XLSX files from `data/raw/archive.zip` with:

```powershell
python -m src.data.extract_data --overwrite
```

Run the preprocessing pipeline against the extracted dataset files:

```powershell
python -m src.pipeline.data_pipeline
```

The pipeline accepts `--input`, `--output-dir`, `--snapshot-date`, and
`--cancellation-prefix` options. Its default input is
`data/raw/extracted/`; the input directory must contain exactly one dataset
file. The default RFM snapshot is one day after the latest eligible sale.

Preprocessing rules:

- Rows missing an invoice, product code, numeric quantity or unit price, or
  parseable transaction date are removed.
- `Price` is standardized as `UnitPrice`; `Revenue` is `Quantity * UnitPrice`.
  Parsed `InvoiceDate` also provides `InvoiceMonth`, `InvoiceYear`,
  `InvoiceDay`, and `InvoiceHour`.
- Product codes and descriptions are trimmed and uppercased; description
  whitespace is collapsed. Missing descriptions use the most frequent
  description for that product code, with `UNKNOWN PRODUCT` as the fallback.
- Exact duplicate rows are removed after standardization. Rows for the same
  invoice and product are retained when any source value differs.
- Invoice IDs beginning with the configured cancellation prefix are written
  to `cancellations.csv`. Negative-quantity non-cancellation records are
  written separately to `returns.csv`.
- Eligible sales require a non-cancellation invoice, positive quantity,
  positive unit price, and positive revenue. Missing customer IDs are retained
  in transaction outputs but excluded from the customer-level RFM output.

The pipeline writes `cleaned_transactions.csv`, `cancellations.csv`,
`returns.csv`, `eligible_sales.csv`, `market_basket_transactions.csv` (one
row per invoice with a JSON list of product codes), and `customer_rfm.csv` to
`data/processed/`. The raw archive and processed datasets remain ignored by
Git.

## Current status

Phase 2 extraction, validation, preprocessing, Phase 3 MySQL integration,
customer segmentation, and the Streamlit frontend are implemented.

## Phase 3: MySQL integration

Install and start MySQL Community Server before running these commands;
MySQL Workbench is an optional graphical client.

Install the requirements, then fill in `DB_HOST`, `DB_PORT`, `DB_NAME`,
`DB_USER`, and `DB_PASSWORD` in the local `.env` file. `.env` is ignored by Git;
never put database credentials in source code or commit them. The default
database name is `retail_intelligence`. Create it once in MySQL Workbench if it
does not exist:

```sql
CREATE DATABASE IF NOT EXISTS retail_intelligence;
```

Test the connection and load the processed transactions from PowerShell in the
project directory:

```powershell
python -m src.database.connection
python -m src.database.load_to_mysql
```

The loader creates the `customers`, `products`, `invoices`, and
`sales_transactions` tables, then upserts records in one transaction. A stable
SHA-256 source key prevents the same cleaned transaction from being inserted
again when a load is rerun. Sales, returns, cancellations, and other cleaned
records are preserved; revenue reports filter to eligible `sale` records.
Product categories are not added because they are not present in the source.
The loader chooses a product's most frequent description, with a lexical
tie-break, and uses the earliest line date as an invoice's header date. The
original line date and description remain on each sales transaction.

In MySQL Workbench, connect to the configured server, select the
`retail_intelligence` schema, and refresh the **Schemas** panel to inspect the
tables. The five analytics queries are available as
`ANALYTICS_QUERIES` in `src/database/load_to_mysql.py`.

## Streamlit dashboard

Start the frontend from the project directory:

```powershell
python -m streamlit run app.py
```

Or use the project entry point:

```powershell
python main.py
```

The dashboard provides:

- revenue, order, customer, and product KPIs
- monthly revenue and country analysis
- top-product rankings
- RFM customer segmentation with K-Means
- basket-size analysis
- product co-purchase recommendations
- a button to rerun the preprocessing pipeline
- MySQL connection testing and data loading controls

## MySQL setup

The local server must be running before using the MySQL commands. Confirm the
connection and load all processed tables with:

```powershell
python -m src.database.connection
python -m src.database.load_to_mysql
```

The database contains `customers`, `products`, `invoices`, and
`sales_transactions`. The loader is idempotent and uses a stable source key for
transaction deduplication.

## Power BI

The CSV files in `data/processed/` can be loaded directly into Power BI Desktop.
The project includes a setup guide at
`dashboard/powerbi/README.md` and the five SQL analytics queries in
`src/database/load_to_mysql.py`.

Power BI measures are provided in `dashboard/powerbi/measures.dax`. A native
`.pbix` report must be created and saved using Power BI Desktop.

See [DEPLOYMENT.md](./DEPLOYMENT.md) for Streamlit Community Cloud setup and
the processed-data upload workflow.
