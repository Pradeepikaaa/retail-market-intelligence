from __future__ import annotations

import argparse
import hashlib
import json
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd
from sqlalchemy import (
    BigInteger,
    Boolean,
    CHAR,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    text,
)
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.engine import Connection, Engine

from src.database.connection import (
    PROJECT_ROOT,
    create_database_engine,
    load_database_settings,
)


LOGGER = logging.getLogger(__name__)
MONEY_QUANTUM = Decimal("0.0001")
BIGINT_MIN = -(2**63)
BIGINT_MAX = 2**63 - 1

metadata = MetaData()

customers = Table(
    "customers",
    metadata,
    Column("customer_id", BigInteger, primary_key=True),
    Column("recency_days", Integer),
    Column("frequency", Integer),
    Column("monetary", Numeric(16, 4)),
    Column("first_purchase_date", DateTime),
    Column("last_purchase_date", DateTime),
    Column("snapshot_date", DateTime),
    mysql_engine="InnoDB",
    mysql_charset="utf8mb4",
)

products = Table(
    "products",
    metadata,
    Column("stock_code", String(64), primary_key=True),
    Column("description", String(512), nullable=False),
    mysql_engine="InnoDB",
    mysql_charset="utf8mb4",
)

invoices = Table(
    "invoices",
    metadata,
    Column("invoice_id", String(32), primary_key=True),
    Column("customer_id", BigInteger, ForeignKey("customers.customer_id")),
    Column("invoice_date", DateTime, nullable=False),
    mysql_engine="InnoDB",
    mysql_charset="utf8mb4",
)

sales_transactions = Table(
    "sales_transactions",
    metadata,
    Column("source_key", CHAR(64), primary_key=True),
    Column("invoice_id", String(32), ForeignKey("invoices.invoice_id"), nullable=False),
    Column("stock_code", String(64), ForeignKey("products.stock_code"), nullable=False),
    Column("customer_id", BigInteger, ForeignKey("customers.customer_id")),
    Column("invoice_date", DateTime, nullable=False),
    Column("quantity", Integer, nullable=False),
    Column("unit_price", Numeric(16, 4), nullable=False),
    Column("revenue", Numeric(16, 4), nullable=False),
    Column("country", String(128)),
    Column("transaction_type", String(24), nullable=False),
    Column("is_cancellation", Boolean, nullable=False),
    mysql_engine="InnoDB",
    mysql_charset="utf8mb4",
)
Index("ix_sales_transactions_invoice_date", sales_transactions.c.invoice_date)
Index("ix_sales_transactions_transaction_type", sales_transactions.c.transaction_type)
Index("ix_sales_transactions_country", sales_transactions.c.country)
Index("ix_sales_transactions_customer_id", sales_transactions.c.customer_id)


ANALYTICS_QUERIES = {
    "monthly_revenue": """
        SELECT DATE_FORMAT(invoice_date, '%Y-%m') AS invoice_month,
               SUM(revenue) AS revenue
        FROM sales_transactions
        WHERE transaction_type = 'sale'
        GROUP BY DATE_FORMAT(invoice_date, '%Y-%m')
        ORDER BY invoice_month
    """,
    "top_selling_products": """
        SELECT stock_code, SUM(quantity) AS units_sold,
               SUM(revenue) AS revenue
        FROM sales_transactions
        WHERE transaction_type = 'sale'
        GROUP BY stock_code
        ORDER BY units_sold DESC
        LIMIT 10
    """,
    "top_customers": """
        SELECT customer_id, SUM(revenue) AS revenue
        FROM sales_transactions
        WHERE transaction_type = 'sale' AND customer_id IS NOT NULL
        GROUP BY customer_id
        ORDER BY revenue DESC
        LIMIT 10
    """,
    "revenue_by_country": """
        SELECT country, SUM(revenue) AS revenue
        FROM sales_transactions
        WHERE transaction_type = 'sale'
        GROUP BY country
        ORDER BY revenue DESC
    """,
    "monthly_order_volume": """
        SELECT DATE_FORMAT(invoice_date, '%Y-%m') AS invoice_month,
               COUNT(DISTINCT invoice_id) AS order_count
        FROM sales_transactions
        WHERE transaction_type = 'sale'
        GROUP BY DATE_FORMAT(invoice_date, '%Y-%m')
        ORDER BY invoice_month
    """,
}


def _customer_id(value: object) -> Optional[int]:
    if pd.isna(value):
        return None
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Customer ID is not numeric: {value!r}") from exc
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError(f"Customer ID must be a finite integer: {value!r}")
    result = int(number)
    if result < BIGINT_MIN or result > BIGINT_MAX:
        raise ValueError(f"Customer ID is outside the MySQL BIGINT range: {value!r}")
    return result


def _integer(value: object, field_name: str) -> int:
    number = Decimal(str(value))
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError(f"{field_name} must be a finite integer: {value!r}")
    return int(number)


def _money(value: object, field_name: str) -> Decimal:
    try:
        result = Decimal(str(value)).quantize(MONEY_QUANTUM)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} is not a valid decimal amount: {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"{field_name} must be finite: {value!r}")
    return result


def _python_datetime(value: object, field_name: str) -> datetime:
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp) or timestamp.tz is not None:
        raise ValueError(f"{field_name} must be a valid timezone-naive date.")
    return timestamp.to_pydatetime()


def _validate_transactions(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "Invoice",
        "StockCode",
        "Description",
        "Quantity",
        "InvoiceDate",
        "UnitPrice",
        "Customer ID",
        "Country",
        "Revenue",
        "IsCancellation",
        "TransactionType",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(
            "Cleaned transactions are missing required columns: "
            + ", ".join(missing)
        )

    for column in ("Invoice", "StockCode", "Description"):
        frame[column] = frame[column].astype("string").str.strip()
        if frame[column].isna().any() or frame[column].eq("").any():
            raise ValueError(f"{column} contains blank values.")
    frame["Country"] = (
        frame["Country"].astype("string").str.strip().mask(lambda values: values.eq(""))
    )
    frame["Quantity"] = pd.to_numeric(frame["Quantity"], errors="raise")
    frame["UnitPrice"] = pd.to_numeric(frame["UnitPrice"], errors="raise")
    frame["Revenue"] = pd.to_numeric(frame["Revenue"], errors="raise")
    frame["InvoiceDate"] = pd.to_datetime(
        frame["InvoiceDate"], errors="raise", format="ISO8601"
    )
    if frame[["Quantity", "UnitPrice", "Revenue", "InvoiceDate"]].isna().any().any():
        raise ValueError("Required numeric transaction values or dates contain nulls.")
    if not frame["Quantity"].mod(1).eq(0).all():
        raise ValueError("Quantity contains non-integer values.")

    expected_revenue = frame["Quantity"] * frame["UnitPrice"]
    if ((frame["Revenue"] - expected_revenue).abs() > 0.00005).any():
        raise ValueError("Revenue values do not match Quantity multiplied by UnitPrice.")

    frame["Customer ID"] = frame["Customer ID"].map(_customer_id)
    cancellation_values = (
        frame["IsCancellation"].astype("string").str.strip().str.lower()
    )
    cancellation_map = {
        "true": True,
        "false": False,
        "1": True,
        "0": False,
    }
    invalid_cancellations = ~cancellation_values.isin(cancellation_map)
    if invalid_cancellations.any():
        raise ValueError("IsCancellation contains values other than true or false.")
    frame["IsCancellation"] = cancellation_values.map(cancellation_map).astype(bool)
    frame["TransactionType"] = (
        frame["TransactionType"].astype("string").str.strip().str.lower()
    )
    allowed_types = {"sale", "return", "cancellation", "other"}
    invalid_types = ~frame["TransactionType"].isin(allowed_types)
    if invalid_types.any():
        raise ValueError("TransactionType contains an unsupported value.")

    customer_counts = (
        frame.dropna(subset=["Customer ID"])
        .groupby("Invoice", sort=False)["Customer ID"]
        .nunique()
    )
    if customer_counts.gt(1).any():
        raise ValueError("An invoice maps to multiple customer IDs.")
    return frame


def _build_customer_records(
    transactions: pd.DataFrame, rfm: Optional[pd.DataFrame]
) -> List[dict]:
    records: Dict[int, dict] = {
        int(customer_id): {
            "customer_id": int(customer_id),
            "recency_days": None,
            "frequency": None,
            "monetary": None,
            "first_purchase_date": None,
            "last_purchase_date": None,
            "snapshot_date": None,
        }
        for customer_id in transactions["Customer ID"].dropna().unique()
    }
    if rfm is None:
        return [records[key] for key in sorted(records)]

    required = {
        "Customer ID",
        "RecencyDays",
        "Frequency",
        "Monetary",
        "FirstPurchaseDate",
        "LastPurchaseDate",
        "SnapshotDate",
    }
    missing = sorted(required.difference(rfm.columns))
    if missing:
        raise ValueError("Customer RFM file is missing columns: " + ", ".join(missing))

    seen = set()
    for row in rfm.itertuples(index=False, name=None):
        values = dict(zip(rfm.columns, row))
        customer_id = _customer_id(values["Customer ID"])
        if customer_id is None:
            raise ValueError("Customer RFM contains a blank Customer ID.")
        if customer_id in seen:
            raise ValueError(f"Customer RFM contains duplicate Customer ID {customer_id}.")
        seen.add(customer_id)
        records.setdefault(
            customer_id,
            {
                "customer_id": customer_id,
                "recency_days": None,
                "frequency": None,
                "monetary": None,
                "first_purchase_date": None,
                "last_purchase_date": None,
                "snapshot_date": None,
            },
        )
        records[customer_id].update(
            {
                "recency_days": _integer(values["RecencyDays"], "RecencyDays"),
                "frequency": _integer(values["Frequency"], "Frequency"),
                "monetary": _money(values["Monetary"], "Monetary"),
                "first_purchase_date": _python_datetime(
                    values["FirstPurchaseDate"], "FirstPurchaseDate"
                ),
                "last_purchase_date": _python_datetime(
                    values["LastPurchaseDate"], "LastPurchaseDate"
                ),
                "snapshot_date": _python_datetime(
                    values["SnapshotDate"], "SnapshotDate"
                ),
            }
        )
    return [records[key] for key in sorted(records)]


def _build_product_records(transactions: pd.DataFrame) -> List[dict]:
    counts = (
        transactions.groupby(["StockCode", "Description"], sort=True, dropna=False)
        .size()
        .rename("description_count")
        .reset_index()
        .sort_values(
            ["StockCode", "description_count", "Description"],
            ascending=[True, False, True],
            kind="mergesort",
        )
    )
    selected = counts.drop_duplicates("StockCode")
    return [
        {"stock_code": str(row.StockCode), "description": str(row.Description)}
        for row in selected.itertuples(index=False)
    ]


def _build_invoice_records(transactions: pd.DataFrame) -> List[dict]:
    invoice_frame = transactions.groupby("Invoice", sort=True).agg(
        invoice_date=("InvoiceDate", "min"),
        customer_id=("Customer ID", "first"),
    )
    return [
        {
            "invoice_id": str(invoice_id),
            "customer_id": (
                None if pd.isna(row.customer_id) else int(row.customer_id)
            ),
            "invoice_date": _python_datetime(row.invoice_date, "InvoiceDate"),
        }
        for invoice_id, row in invoice_frame.iterrows()
    ]


def _transaction_row(values: Tuple[object, ...]) -> dict:
    (
        invoice,
        stock_code,
        description,
        quantity,
        invoice_date,
        unit_price,
        customer_id,
        country,
        revenue,
        is_cancellation,
        transaction_type,
    ) = values
    invoice_date_value = _python_datetime(invoice_date, "InvoiceDate")
    unit_price_value = _money(unit_price, "UnitPrice")
    revenue_value = _money(revenue, "Revenue")
    normalized_key = [
        str(invoice),
        str(stock_code),
        str(description),
        _integer(quantity, "Quantity"),
        invoice_date_value.isoformat(sep=" "),
        str(unit_price_value),
        None if pd.isna(customer_id) else _customer_id(customer_id),
        None if pd.isna(country) else str(country),
        str(revenue_value),
        bool(is_cancellation),
        str(transaction_type),
    ]
    source_key = hashlib.sha256(
        json.dumps(normalized_key, ensure_ascii=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return {
        "source_key": source_key,
        "invoice_id": str(invoice),
        "stock_code": str(stock_code),
        "customer_id": (
            None if pd.isna(customer_id) else _customer_id(customer_id)
        ),
        "invoice_date": invoice_date_value,
        "quantity": _integer(quantity, "Quantity"),
        "unit_price": unit_price_value,
        "revenue": revenue_value,
        "country": None if pd.isna(country) else str(country),
        "transaction_type": str(transaction_type),
        "is_cancellation": bool(is_cancellation),
    }


def _iter_transaction_batches(
    transactions: pd.DataFrame, batch_size: int
) -> Iterable[List[dict]]:
    columns = [
        "Invoice",
        "StockCode",
        "Description",
        "Quantity",
        "InvoiceDate",
        "UnitPrice",
        "Customer ID",
        "Country",
        "Revenue",
        "IsCancellation",
        "TransactionType",
    ]
    for start in range(0, len(transactions), batch_size):
        chunk = transactions.iloc[start : start + batch_size]
        yield [
            _transaction_row(values)
            for values in chunk[columns].itertuples(index=False, name=None)
        ]


def _upsert_batches(
    connection: Connection,
    table: Table,
    records: Iterable[List[dict]],
) -> int:
    statement = mysql_insert(table)
    update_values = {
        column.name: statement.inserted[column.name]
        for column in table.columns
        if not column.primary_key
    }
    statement = statement.on_duplicate_key_update(**update_values)
    count = 0
    for batch in records:
        if batch:
            connection.execute(statement, batch)
            count += len(batch)
    LOGGER.info("Upserted %s rows into %s.", f"{count:,}", table.name)
    return count


def load_processed_data(
    input_path: Path,
    rfm_path: Optional[Path],
    batch_size: int = 2000,
    env_file: Optional[Path] = None,
) -> Dict[str, int]:
    if not 1 <= batch_size <= 5000:
        raise ValueError("batch_size must be between 1 and 5000.")
    if not input_path.is_file():
        raise FileNotFoundError(f"Processed transaction file not found: {input_path}")
    if rfm_path is not None and not rfm_path.is_file():
        raise FileNotFoundError(f"Customer RFM file not found: {rfm_path}")

    LOGGER.info("Reading processed transactions from %s", input_path)
    transactions = pd.read_csv(
        input_path,
        dtype={
            "Invoice": "string",
            "StockCode": "string",
            "Description": "string",
            "Customer ID": "string",
            "Country": "string",
            "TransactionType": "string",
        },
    )
    _validate_transactions(transactions)
    rfm = (
        pd.read_csv(rfm_path, dtype={"Customer ID": "string"})
        if rfm_path is not None
        else None
    )

    customer_records = _build_customer_records(transactions, rfm)
    product_records = _build_product_records(transactions)
    invoice_records = _build_invoice_records(transactions)
    LOGGER.info(
        "Prepared %s customers, %s products, %s invoices, and %s transactions.",
        f"{len(customer_records):,}",
        f"{len(product_records):,}",
        f"{len(invoice_records):,}",
        f"{len(transactions):,}",
    )

    settings = load_database_settings(env_file)
    engine = create_database_engine(settings)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        LOGGER.info("Creating database tables if they do not already exist.")
        metadata.create_all(engine)

        with engine.begin() as connection:
            _upsert_batches(
                connection,
                customers,
                (customer_records[start : start + batch_size]
                 for start in range(0, len(customer_records), batch_size)),
            )
            _upsert_batches(
                connection,
                products,
                (product_records[start : start + batch_size]
                 for start in range(0, len(product_records), batch_size)),
            )
            _upsert_batches(
                connection,
                invoices,
                (invoice_records[start : start + batch_size]
                 for start in range(0, len(invoice_records), batch_size)),
            )
            _upsert_batches(
                connection,
                sales_transactions,
                _iter_transaction_batches(transactions, batch_size),
            )
    finally:
        engine.dispose()

    return {
        "customers": len(customer_records),
        "products": len(product_records),
        "invoices": len(invoice_records),
        "sales_transactions": len(transactions),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load processed retail transactions into MySQL."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=PROJECT_ROOT / "data" / "processed" / "cleaned_transactions.csv",
        help="Cleaned transaction CSV (includes sales, returns, and cancellations).",
    )
    parser.add_argument(
        "--rfm",
        default=str(PROJECT_ROOT / "data" / "processed" / "customer_rfm.csv"),
        help="Customer-level RFM CSV; pass an empty string to skip RFM fields.",
    )
    parser.add_argument("--batch-size", type=int, default=2000)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    rfm_path = Path(args.rfm) if args.rfm else None
    try:
        counts = load_processed_data(
            args.input,
            rfm_path,
            batch_size=args.batch_size,
            env_file=args.env_file,
        )
    except Exception:
        LOGGER.exception("MySQL data loading failed.")
        return 1

    LOGGER.info("MySQL data loading completed: %s", counts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
