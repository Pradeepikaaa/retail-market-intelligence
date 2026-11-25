from __future__ import annotations

from io import BytesIO
from typing import Mapping

import pandas as pd


REQUIRED_UPLOADS = {
    "eligible_sales.csv",
    "customer_rfm.csv",
    "market_basket_transactions.csv",
}


def load_uploaded_datasets(
    uploaded_files: Mapping[str, bytes],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    missing_files = sorted(REQUIRED_UPLOADS.difference(uploaded_files))
    if missing_files:
        raise ValueError(
            "Upload all required processed files: " + ", ".join(missing_files)
        )

    sales = pd.read_csv(
        BytesIO(uploaded_files["eligible_sales.csv"]),
        parse_dates=["InvoiceDate"],
        dtype={
            "Invoice": "string",
            "StockCode": "string",
            "Description": "string",
            "Country": "string",
        },
        low_memory=False,
    )
    rfm = pd.read_csv(
        BytesIO(uploaded_files["customer_rfm.csv"]),
        dtype={"Customer ID": "string"},
        low_memory=False,
    )
    baskets = pd.read_csv(
        BytesIO(uploaded_files["market_basket_transactions.csv"]),
        dtype={"Invoice": "string", "Items": "string"},
        low_memory=False,
    )

    required_columns = (
        (sales, {"Invoice", "StockCode", "Description", "InvoiceDate", "Revenue", "Quantity", "Customer ID", "Country"}),
        (rfm, {"Customer ID", "RecencyDays", "Frequency", "Monetary"}),
        (baskets, {"Invoice", "Items", "ItemCount"}),
    )
    for frame, expected_columns in required_columns:
        missing_columns = sorted(expected_columns.difference(frame.columns))
        if missing_columns:
            raise ValueError(
                "Uploaded dataset is missing required columns: "
                + ", ".join(missing_columns)
            )
        if frame.empty:
            raise ValueError("Uploaded processed datasets must not be empty.")

    return sales, rfm, baskets
