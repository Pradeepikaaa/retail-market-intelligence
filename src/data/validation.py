from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Hashable, List, Optional, Sequence, Tuple

import pandas as pd

from src.data.load_data import discover_dataset_files, load_data


CUSTOMER_COLUMN_ALIASES = (
    "customerid",
    "customernumber",
    "customerno",
    "customer",
    "clientid",
    "client",
)
PRODUCT_COLUMN_ALIASES = (
    "productid",
    "productcode",
    "stockcode",
    "sku",
    "itemcode",
    "itemid",
    "product",
    "item",
)
DATE_COLUMN_ALIASES = (
    "transactiondate",
    "invoicedate",
    "orderdate",
    "purchasedate",
    "timestamp",
    "date",
)
REQUIRED_COLUMN_ALIASES = {
    "Invoice": ("invoice", "invoiceno", "invoicenumber", "transactionid"),
    "StockCode": ("stockcode", "productcode", "productid", "sku", "itemcode"),
    "Description": (
        "description",
        "productdescription",
        "productname",
        "itemdescription",
    ),
    "Quantity": ("quantity", "qty"),
    "InvoiceDate": ("invoicedate", "transactiondate", "orderdate", "date"),
    "UnitPrice": ("unitprice", "price", "itemprice"),
    "Customer ID": (
        "customerid",
        "customernumber",
        "customerno",
        "customer",
        "clientid",
    ),
}


@dataclass(frozen=True)
class DatasetSummary:
    row_count: int
    column_count: int
    column_names: Tuple[str, ...]
    data_types: Dict[str, str]
    missing_values: Dict[str, int]
    duplicate_records: int
    customer_column: Optional[str]
    unique_customers: Optional[int]
    product_column: Optional[str]
    unique_products: Optional[int]
    date_column: Optional[str]
    transaction_date_start: Optional[str]
    transaction_date_end: Optional[str]
    unparseable_transaction_dates: Optional[int]


def _normalize_column_name(column: Hashable) -> str:
    return re.sub(r"[^a-z0-9]", "", str(column).casefold())


def _find_column(
    columns: Sequence[Hashable], aliases: Sequence[str]
) -> Optional[Hashable]:
    normalized_columns = {
        _normalize_column_name(column): column for column in columns
    }
    for alias in aliases:
        if alias in normalized_columns:
            return normalized_columns[alias]
    return None


def validate_required_columns(dataframe: pd.DataFrame) -> Dict[str, Hashable]:
    normalized_columns: Dict[str, List[Hashable]] = {}
    for column in dataframe.columns:
        normalized_columns.setdefault(_normalize_column_name(column), []).append(
            column
        )

    mapping: Dict[str, Hashable] = {}
    missing_columns = []
    for canonical_name, aliases in REQUIRED_COLUMN_ALIASES.items():
        matches = []
        for alias in aliases:
            for column in normalized_columns.get(alias, []):
                if column not in matches:
                    matches.append(column)
        if not matches:
            missing_columns.append(canonical_name)
        elif len(matches) > 1:
            raise ValueError(
                f"Multiple source columns match {canonical_name}: {matches}"
            )
        else:
            mapping[canonical_name] = matches[0]

    if missing_columns:
        raise ValueError(
            "Missing required columns: " + ", ".join(missing_columns)
        )
    return mapping


def parse_transaction_dates(values: pd.Series) -> pd.Series:
    if pd.api.types.is_datetime64_any_dtype(values.dtype):
        return pd.to_datetime(values, errors="coerce")

    iso_dates = pd.to_datetime(values, errors="coerce", format="ISO8601")
    non_missing = int(values.notna().sum())
    if int(iso_dates.notna().sum()) == non_missing:
        return iso_dates

    month_first = pd.to_datetime(
        values, errors="coerce", format="mixed", dayfirst=False
    )
    day_first = pd.to_datetime(
        values, errors="coerce", format="mixed", dayfirst=True
    )
    month_first_count = int(month_first.notna().sum())
    day_first_count = int(day_first.notna().sum())
    if month_first_count > day_first_count:
        return month_first
    if day_first_count > month_first_count:
        return day_first

    ambiguous = (
        month_first.notna()
        & day_first.notna()
        & month_first.ne(day_first)
    )
    if bool(ambiguous.any()):
        raise ValueError(
            "Transaction dates are ambiguous between month-first and day-first "
            "formats; provide a consistent date format before reporting a range."
        )
    return month_first


def summarize_dataframe(dataframe: pd.DataFrame) -> DatasetSummary:
    customer_column = _find_column(dataframe.columns, CUSTOMER_COLUMN_ALIASES)
    product_column = _find_column(dataframe.columns, PRODUCT_COLUMN_ALIASES)
    date_column = _find_column(dataframe.columns, DATE_COLUMN_ALIASES)

    unique_customers = (
        int(dataframe[customer_column].nunique(dropna=True))
        if customer_column is not None
        else None
    )
    unique_products = (
        int(dataframe[product_column].nunique(dropna=True))
        if product_column is not None
        else None
    )

    date_start = None
    date_end = None
    unparseable_dates = None
    if date_column is not None:
        raw_dates = dataframe[date_column]
        parsed_dates = parse_transaction_dates(raw_dates)
        valid_dates = parsed_dates.dropna()
        unparseable_dates = int((raw_dates.notna() & parsed_dates.isna()).sum())
        if not valid_dates.empty:
            date_start = str(valid_dates.min())
            date_end = str(valid_dates.max())

    return DatasetSummary(
        row_count=int(dataframe.shape[0]),
        column_count=int(dataframe.shape[1]),
        column_names=tuple(str(column) for column in dataframe.columns),
        data_types={
            str(column): str(dtype)
            for column, dtype in dataframe.dtypes.items()
        },
        missing_values={
            str(column): int(count)
            for column, count in dataframe.isna().sum().items()
        },
        duplicate_records=int(dataframe.duplicated().sum()),
        customer_column=(
            str(customer_column) if customer_column is not None else None
        ),
        unique_customers=unique_customers,
        product_column=str(product_column) if product_column is not None else None,
        unique_products=unique_products,
        date_column=str(date_column) if date_column is not None else None,
        transaction_date_start=date_start,
        transaction_date_end=date_end,
        unparseable_transaction_dates=unparseable_dates,
    )


def print_summary(dataset_path: Path, summary: DatasetSummary) -> None:
    print(f"Dataset: {dataset_path}")
    print(f"Rows: {summary.row_count:,}")
    print(f"Columns: {summary.column_count:,}")
    print("Column names:")
    for column in summary.column_names:
        print(f"  {column}")
    print("Data types:")
    for column, dtype in summary.data_types.items():
        print(f"  {column}: {dtype}")
    print("Missing values:")
    for column, count in summary.missing_values.items():
        print(f"  {column}: {count:,}")
    print(f"Duplicate records: {summary.duplicate_records:,}")
    if summary.customer_column is None:
        print("Unique customers: not identified (no recognized customer column)")
    else:
        print(
            f"Unique customers ({summary.customer_column}): "
            f"{summary.unique_customers:,}"
        )
    if summary.product_column is None:
        print("Unique products: not identified (no recognized product column)")
    else:
        print(
            f"Unique products ({summary.product_column}): "
            f"{summary.unique_products:,}"
        )
    if summary.date_column is None:
        print("Transaction date range: not identified (no recognized date column)")
    elif summary.transaction_date_start is None:
        print(
            f"Transaction date range ({summary.date_column}): "
            "no parseable dates"
        )
        print(
            "Unparseable transaction dates: "
            f"{summary.unparseable_transaction_dates:,}"
        )
    else:
        print(
            f"Transaction date range ({summary.date_column}): "
            f"{summary.transaction_date_start} to "
            f"{summary.transaction_date_end}"
        )
        print(
            "Unparseable transaction dates: "
            f"{summary.unparseable_transaction_dates:,}"
        )


def main(argv: Optional[Sequence[str]] = None) -> int:
    project_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Load extracted retail data and report data quality metrics."
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=project_root / "data" / "raw" / "extracted",
        help="Dataset file or directory to inspect recursively.",
    )
    args = parser.parse_args(argv)

    for dataset_path in discover_dataset_files(args.path):
        dataframe = load_data(dataset_path)
        summary = summarize_dataframe(dataframe)
        print_summary(dataset_path, summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
