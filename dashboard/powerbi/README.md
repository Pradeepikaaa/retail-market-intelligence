# Power BI Dashboard Setup

Open Power BI Desktop and create a new report.

## Recommended data sources

Choose **Text/CSV** for these files:

- `data/processed/eligible_sales.csv`
- `data/processed/customer_rfm.csv`
- `data/processed/market_basket_transactions.csv`

These files cover sales, customer segments, and basket analysis. The raw and
processed directories are intentionally local and excluded from Git.

## Suggested report pages

1. **Executive overview**
   - total revenue
   - number of invoices
   - active customers
   - monthly revenue line chart
   - revenue by country map or bar chart
2. **Product performance**
   - top products by revenue
   - top products by quantity
   - product-level filter
3. **Customer analytics**
   - RFM table
   - recency, frequency, and monetary charts
   - use the segment field produced by the Streamlit segmentation workflow
4. **Basket insights**
   - average and maximum basket size
   - invoice basket distribution

## Optional MySQL source

Power BI can connect directly to MySQL using its **Get Data > MySQL database**
connector. Use the host and database from `.env`, then select:

- `customers`
- `products`
- `invoices`
- `sales_transactions`

For the MySQL star schema, create single-direction, one-to-many relationships:

- `customers[customer_id]` -> `sales_transactions[customer_id]`
- `products[stock_code]` -> `sales_transactions[stock_code]`
- `invoices[invoice_id]` -> `sales_transactions[invoice_id]`

Do not also relate `customers` to `invoices` while the customer-to-fact
relationship is active; that introduces a second filter path. The ready-to-add
measures are in [`measures.dax`](./measures.dax). This guide and measures file
are not a `.pbix`; that file must be saved and validated in Power BI Desktop.
