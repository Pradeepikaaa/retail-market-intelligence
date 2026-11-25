from __future__ import annotations

import pandas as pd


def monthly_revenue(sales: pd.DataFrame) -> pd.DataFrame:
    result = (
        sales.assign(InvoiceDate=pd.to_datetime(sales["InvoiceDate"], errors="coerce"))
        .dropna(subset=["InvoiceDate"])
        .assign(Month=lambda frame: frame["InvoiceDate"].dt.to_period("M").astype(str))
        .groupby("Month", as_index=False)
        .agg(Revenue=("Revenue", "sum"), Orders=("Invoice", "nunique"))
    )
    return result.sort_values("Month")


def top_products(sales: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    result = (
        sales.groupby(["StockCode", "Description"], as_index=False)
        .agg(Units=("Quantity", "sum"), Revenue=("Revenue", "sum"))
        .sort_values(["Revenue", "Units"], ascending=False)
    )
    return result.head(limit)


def revenue_by_country(sales: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    result = (
        sales.dropna(subset=["Country"])
        .groupby("Country", as_index=False)
        .agg(Revenue=("Revenue", "sum"), Orders=("Invoice", "nunique"))
        .sort_values("Revenue", ascending=False)
    )
    return result.head(limit)


def kpi_summary(sales: pd.DataFrame) -> dict[str, float | int]:
    return {
        "revenue": float(sales["Revenue"].sum()),
        "orders": int(sales["Invoice"].nunique()),
        "customers": int(sales["Customer ID"].dropna().nunique()),
        "products": int(sales["StockCode"].nunique()),
    }


def numeric_summary(frame: pd.DataFrame) -> pd.DataFrame:
    numeric_columns = frame.select_dtypes(include="number")
    if numeric_columns.empty:
        return pd.DataFrame()
    return numeric_columns.describe()
