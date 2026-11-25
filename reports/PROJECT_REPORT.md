# Retail Market Intelligence Project Report

## Executive summary

This project turns the Online Retail II transaction dataset into a local retail
analytics application. It cleans raw invoice lines, calculates transaction and
customer metrics, stores normalized transaction data in MySQL, and serves
interactive sales analysis, customer segmentation, and product co-purchase
recommendations through Streamlit.

## Dataset and scope

The completed local run processed 1,067,371 source rows. It produced 1,033,036
deduplicated cleaned transaction rows, including 19,104 cancellation rows and
3,393 return rows. Eligible positive sales comprise 1,007,913 rows. The
transactions span 1 December 2009 through 9 December 2011.

The outputs contain 40,077 invoice baskets, 5,878 customers with eligible sales
and usable customer IDs for RFM analysis, and 4,745 products in eligible sales.
The RFM customer count is smaller than the MySQL customer dimension because
transaction rows without a customer ID are retained in the database.

## Methods

### Data preparation

- Standardize invoice, product, date, quantity, unit price, and customer fields.
- Remove invalid required transaction values and exact duplicate rows.
- Derive revenue as quantity multiplied by unit price.
- Keep cancellations and returns separately identifiable.
- Define eligible sales as positive, non-cancellation transactions.

### Sales analysis

Revenue, distinct invoices, distinct identified customers, and distinct
products are summarized from eligible sales. Monthly and country summaries and
top-product rankings are available in the dashboard.

### Customer analysis

RFM features are recency in days, distinct invoice frequency, and monetary
sales value. A standardized K-Means model groups customers into five clusters;
human-readable labels are assigned from each cluster's average RFM profile.
These are exploratory segments, not validated predictions of future behavior.

### Product recommendations

Each invoice is treated as a basket. For a selected product, the recommender
counts other products that appear in the same invoice and ranks them by
co-occurrence. This is basket-level association, not personalized
recommendation or proof that one product causes another purchase.

## Results

- Eligible-sales revenue: **$20,476,260.45**
- Distinct invoices: **40,077**
- Identified RFM customers: **5,878**
- Products: **4,745**
- Countries: **43**
- Average distinct products per invoice: **24.9**
- Largest basket: **1,108 distinct products**
- United Kingdom revenue: **$17,410,196.12** across 36,535 invoices

Top products by revenue in the current processed dataset:

| Stock code | Product | Revenue |
|---|---|---:|
| M | MANUAL | $339,241.29 |
| 22423 | REGENCY CAKESTAND 3 TIER | $330,590.32 |
| DOT | DOTCOM POSTAGE | $309,854.11 |
| 85123A | WHITE HANGING HEART T-LIGHT HOLDER | $260,990.22 |
| 23843 | PAPER CRAFT, LITTLE BIRDIE | $168,469.60 |

The high revenue of service-like stock codes such as `M` and `DOT` should be
reviewed before using product rankings for merchandising decisions.

## Database and application

The local MySQL database contains `customers`, `products`, `invoices`, and
`sales_transactions`. The last verified load contained 5,942 customer records,
5,131 product records, 53,628 invoices, and 1,033,036 transaction records.
These row counts include the broader cleaned transaction population rather
than eligible sales alone.

The Streamlit application provides date and country filters, sales KPIs,
monthly revenue and country charts, product rankings, RFM clusters, basket
statistics, product co-purchase recommendations, and local pipeline/database
controls.

## Limitations and next steps

- Findings describe this historical dataset and should not be treated as
  current market demand.
- No product category, inventory, cost, or margin data is available, so the
  analysis cannot calculate profitability or stock recommendations.
- K-Means and cluster labels are exploratory and should be validated with
  business stakeholders before operational use.
- Co-occurrence counts do not account for product popularity, seasonality, or
  association-rule confidence and lift.
- The project contains Power BI connection guidance, not a finished `.pbix`
  report file. Create and validate the report in Power BI Desktop.
- Online hosting is not configured. The current app reads ignored local
  processed CSVs and uses local database configuration; deployment requires a
  repository and a hosted data source or secure data-upload workflow.

## Reproducibility

From the project directory in PowerShell:

```powershell
python -m src.pipeline.data_pipeline
python -m src.database.connection
python -m src.database.load_to_mysql
python -m pytest -q
python -m streamlit run app.py
```
