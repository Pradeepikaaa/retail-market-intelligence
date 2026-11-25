from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

import pandas as pd

from src.data.load_data import discover_dataset_files, load_data
from src.data.validation import parse_transaction_dates, validate_required_columns


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreprocessingConfig:
    input_path: Union[str, Path]
    output_dir: Union[str, Path]
    snapshot_date: Optional[str] = None
    cancellation_prefix: str = "C"
    unknown_description: str = "UNKNOWN PRODUCT"


@dataclass(frozen=True)
class PreprocessingResult:
    record_counts: Dict[str, int]
    output_paths: Dict[str, Path]


def preprocess_dataframe(
    dataframe: pd.DataFrame,
    cancellation_prefix: str = "C",
    unknown_description: str = "UNKNOWN PRODUCT",
) -> Tuple[pd.DataFrame, Dict[str, int]]:
    """Normalize required fields, fill descriptions, and remove exact duplicates.

    Duplicate rows are removed only when every standardized source column matches.
    Rows sharing an invoice and product are retained when any source value differs.
    """
    if not cancellation_prefix.strip():
        raise ValueError("cancellation_prefix must not be empty")
    if not unknown_description.strip():
        raise ValueError("unknown_description must not be empty")

    column_mapping = validate_required_columns(dataframe)
    LOGGER.info("Validated required columns: %s", column_mapping)
    records_loaded = len(dataframe)

    transactions = dataframe.rename(
        columns={source: canonical for canonical, source in column_mapping.items()}
    ).copy()

    transactions["Invoice"] = (
        transactions["Invoice"].astype("string").str.strip().mask(lambda s: s.eq(""))
    )
    transactions["StockCode"] = (
        transactions["StockCode"]
        .astype("string")
        .str.strip()
        .str.upper()
        .mask(lambda s: s.eq(""))
    )
    transactions["Description"] = (
        transactions["Description"]
        .astype("string")
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
        .str.upper()
        .mask(lambda s: s.eq(""))
    )
    transactions["Quantity"] = pd.to_numeric(
        transactions["Quantity"], errors="coerce"
    )
    transactions["UnitPrice"] = pd.to_numeric(
        transactions["UnitPrice"], errors="coerce"
    )
    transactions["InvoiceDate"] = parse_transaction_dates(
        transactions["InvoiceDate"]
    )

    customer_ids = (
        transactions["Customer ID"]
        .astype("string")
        .str.strip()
        .mask(lambda s: s.eq(""))
    )
    numeric_customer_ids = pd.to_numeric(customer_ids, errors="coerce")
    non_missing_customer_ids = customer_ids.notna()
    numeric_ids_are_complete = (
        int(numeric_customer_ids.notna().sum())
        == int(non_missing_customer_ids.sum())
    )
    numeric_ids_are_integers = bool(
        numeric_customer_ids.dropna().mod(1).eq(0).all()
    )
    if numeric_ids_are_complete and numeric_ids_are_integers:
        transactions["Customer ID"] = numeric_customer_ids.astype("Int64")
    else:
        transactions["Customer ID"] = customer_ids

    required_transaction_fields = [
        "Invoice",
        "StockCode",
        "Quantity",
        "InvoiceDate",
        "UnitPrice",
    ]
    invalid_required = transactions[required_transaction_fields].isna().any(axis=1)
    invalid_required_count = int(invalid_required.sum())
    transactions = transactions.loc[~invalid_required].copy()

    description_missing = transactions["Description"].isna()
    description_counts = (
        transactions.loc[~description_missing]
        .groupby(["StockCode", "Description"], sort=True)
        .size()
        .rename("DescriptionCount")
        .reset_index()
        .sort_values(
            ["StockCode", "DescriptionCount", "Description"],
            ascending=[True, False, True],
            kind="mergesort",
        )
    )
    description_by_product = (
        description_counts.drop_duplicates("StockCode")
        .set_index("StockCode")["Description"]
    )
    inferred_descriptions = transactions.loc[description_missing, "StockCode"].map(
        description_by_product
    )
    inferred_count = int(inferred_descriptions.notna().sum())
    transactions.loc[description_missing, "Description"] = inferred_descriptions

    unresolved_descriptions = transactions["Description"].isna()
    unresolved_count = int(unresolved_descriptions.sum())
    transactions.loc[unresolved_descriptions, "Description"] = (
        unknown_description.strip().upper()
    )

    records_before_deduplication = len(transactions)
    transactions = transactions.drop_duplicates(keep="first").copy()
    duplicate_count = records_before_deduplication - len(transactions)

    transactions["Revenue"] = transactions["Quantity"] * transactions["UnitPrice"]
    transactions["InvoiceMonth"] = transactions["InvoiceDate"].dt.strftime("%Y-%m")
    transactions["InvoiceYear"] = transactions["InvoiceDate"].dt.year.astype("int64")
    transactions["InvoiceDay"] = transactions["InvoiceDate"].dt.day.astype("int64")
    transactions["InvoiceHour"] = transactions["InvoiceDate"].dt.hour.astype("int64")

    normalized_invoices = transactions["Invoice"].str.upper()
    is_cancellation = normalized_invoices.str.startswith(
        cancellation_prefix.strip().upper(), na=False
    )
    transactions["IsCancellation"] = is_cancellation
    transaction_type = pd.Series("other", index=transactions.index, dtype="string")
    transaction_type.loc[is_cancellation] = "cancellation"
    transaction_type.loc[~is_cancellation & transactions["Quantity"].lt(0)] = "return"
    transaction_type.loc[
        ~is_cancellation
        & transactions["Quantity"].gt(0)
        & transactions["UnitPrice"].gt(0)
        & transactions["Revenue"].gt(0)
    ] = "sale"
    transactions["TransactionType"] = transaction_type

    record_counts = {
        "records_loaded": records_loaded,
        "records_after_required_column_validation": records_loaded,
        "records_dropped_for_missing_or_invalid_transaction_fields": (
            invalid_required_count
        ),
        "records_before_exact_duplicate_removal": records_before_deduplication,
        "exact_duplicate_records_removed": duplicate_count,
        "descriptions_inferred_from_product_code": inferred_count,
        "descriptions_filled_as_unknown": unresolved_count,
        "cleaned_records": len(transactions),
    }
    return transactions, record_counts


def _build_market_basket_transactions(
    eligible_sales: pd.DataFrame,
) -> pd.DataFrame:
    columns = [
        "Invoice",
        "InvoiceDate",
        "Customer ID",
        "Items",
        "ItemCount",
        "TotalQuantity",
        "TotalRevenue",
    ]
    if eligible_sales.empty:
        return pd.DataFrame(columns=columns)

    grouped = eligible_sales.groupby("Invoice", sort=True)
    baskets = grouped.agg(
        InvoiceDate=("InvoiceDate", "min"),
        TotalQuantity=("Quantity", "sum"),
        TotalRevenue=("Revenue", "sum"),
    )
    baskets["Customer ID"] = grouped["Customer ID"].first()
    baskets["Items"] = grouped["StockCode"].agg(
        lambda values: json.dumps(sorted(set(values.dropna().astype(str))))
    )
    baskets["ItemCount"] = grouped["StockCode"].nunique()
    return baskets.reset_index()[columns]


def _build_customer_rfm(
    eligible_sales: pd.DataFrame,
    snapshot_date: Optional[str],
) -> Tuple[pd.DataFrame, Optional[pd.Timestamp], int]:
    columns = [
        "Customer ID",
        "RecencyDays",
        "Frequency",
        "Monetary",
        "FirstPurchaseDate",
        "LastPurchaseDate",
        "SnapshotDate",
    ]
    missing_customer_count = int(eligible_sales["Customer ID"].isna().sum())
    customer_sales = eligible_sales.dropna(subset=["Customer ID"])
    if customer_sales.empty:
        return pd.DataFrame(columns=columns), None, missing_customer_count

    last_sale_date = customer_sales["InvoiceDate"].max()
    if snapshot_date is None:
        snapshot = last_sale_date + pd.Timedelta(days=1)
    else:
        snapshot = pd.Timestamp(
            pd.to_datetime(snapshot_date, errors="raise", format="ISO8601")
        )
        if snapshot.tz is not None:
            raise ValueError("snapshot_date must be timezone-naive.")
        if snapshot < last_sale_date:
            raise ValueError(
                "snapshot_date must be on or after the latest eligible sale date."
            )

    grouped = customer_sales.groupby("Customer ID", sort=True)
    rfm = grouped.agg(
        FirstPurchaseDate=("InvoiceDate", "min"),
        LastPurchaseDate=("InvoiceDate", "max"),
        Frequency=("Invoice", "nunique"),
        Monetary=("Revenue", "sum"),
    )
    rfm["RecencyDays"] = (snapshot - rfm["LastPurchaseDate"]).dt.days
    rfm["SnapshotDate"] = snapshot
    return rfm.reset_index()[columns], snapshot, missing_customer_count


def run_preprocessing(config: PreprocessingConfig) -> PreprocessingResult:
    LOGGER.info("Discovering raw dataset files under %s", config.input_path)
    dataset_files = discover_dataset_files(config.input_path)
    if len(dataset_files) != 1:
        raise ValueError(
            f"Expected exactly one raw dataset file; found {len(dataset_files)}. "
            "Pass the specific CSV, XLS, or XLSX file as input."
        )

    source_path = dataset_files[0]
    LOGGER.info("Loading raw dataset: %s", source_path)
    raw_data = load_data(source_path)
    LOGGER.info(
        "Loaded %s records and %s columns",
        f"{len(raw_data):,}",
        len(raw_data.columns),
    )

    cleaned, record_counts = preprocess_dataframe(
        raw_data,
        cancellation_prefix=config.cancellation_prefix,
        unknown_description=config.unknown_description,
    )

    cancellations = cleaned.loc[cleaned["TransactionType"].eq("cancellation")].copy()
    returns = cleaned.loc[cleaned["TransactionType"].eq("return")].copy()
    eligible_sales = cleaned.loc[cleaned["TransactionType"].eq("sale")].copy()
    market_baskets = _build_market_basket_transactions(eligible_sales)
    customer_rfm, snapshot, missing_customer_count = _build_customer_rfm(
        eligible_sales,
        config.snapshot_date,
    )

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    datasets = {
        "cleaned_transactions": cleaned,
        "cancellations": cancellations,
        "returns": returns,
        "eligible_sales": eligible_sales,
        "market_basket_transactions": market_baskets,
        "customer_rfm": customer_rfm,
    }
    output_paths = {}
    for dataset_name, dataset in datasets.items():
        output_path = output_dir / f"{dataset_name}.csv"
        dataset.to_csv(
            output_path,
            index=False,
            date_format="%Y-%m-%d %H:%M:%S",
            encoding="utf-8",
        )
        output_paths[dataset_name] = output_path
        LOGGER.info("Saved %s records to %s", f"{len(dataset):,}", output_path)

    record_counts.update(
        {
            "cancellation_records": len(cancellations),
            "return_records": len(returns),
            "eligible_sales_records": len(eligible_sales),
            "eligible_sales_without_customer_id": missing_customer_count,
            "market_basket_transactions": len(market_baskets),
            "rfm_customers": len(customer_rfm),
        }
    )
    if snapshot is not None:
        LOGGER.info("RFM snapshot date: %s", snapshot)
    for stage, count in record_counts.items():
        LOGGER.info("Stage count - %s: %s", stage, f"{count:,}")

    return PreprocessingResult(
        record_counts=record_counts,
        output_paths=output_paths,
    )
