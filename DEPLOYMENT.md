# Streamlit Community Cloud Deployment

## Repository prerequisites

The GitHub repository must contain `app.py`, `main.py`, `requirements.txt`,
`src/`, and the project tests. Do not commit `.env`, database passwords, or
processed/raw data files.

The dashboard can run without a hosted database. When deployed without local
processed files, upload these three files in the app:

- `eligible_sales.csv`
- `customer_rfm.csv`
- `market_basket_transactions.csv`

Create them locally with `python -m src.pipeline.data_pipeline`. The uploaded
files are held in Streamlit session state only; after an app restart or a new
session, upload them again. Avoid using real customer-sensitive data in a
publicly accessible app.

## Deploy

1. Push the latest project files to the GitHub repository.
2. Sign in at Streamlit Community Cloud with GitHub.
3. Choose **Create app**, select the repository and branch, and set the main
   file to `app.py`.
4. Deploy, open the app URL, and upload the three processed CSVs.
5. Confirm the Overview, Customer Segments, Market Basket, and Recommendations
   tabs load successfully.

The GitHub repository should remain free of local datasets and secrets. If
using MySQL features in the hosted dashboard, configure a separately hosted,
network-accessible database and platform secrets. `localhost` refers to the
Streamlit container itself, not the developer's computer; never expose a local
database port to the public internet as a shortcut.

## Local run

```powershell
python -m streamlit run app.py
```

## Current limitation

Push the project files to GitHub before creating the Cloud app. Cloud app
creation is a separate step in Streamlit Community Cloud and is not triggered
by a local run.
