import pandas as pd

from src.analysis.market_analysis import (
    kpi_summary,
    monthly_revenue,
    numeric_summary,
    revenue_by_country,
    top_products,
)
from src.recommendations.product_recommender import ProductRecommender
from src.models.customer_segmentation import segment_customers
from src.data.dashboard_data import load_uploaded_datasets


def test_kpi_summary_and_monthly_revenue():
    sales = pd.DataFrame({
        "Invoice": ["1", "1", "2"],
        "StockCode": ["A", "B", "A"],
        "Customer ID": [10, 10, 20],
        "InvoiceDate": ["2024-01-01", "2024-01-01", "2024-02-01"],
        "Revenue": [10.0, 20.0, 5.0],
        "Quantity": [1, 2, 1],
    })
    assert kpi_summary(sales) == {
        "revenue": 35.0,
        "orders": 2,
        "customers": 2,
        "products": 2,
    }
    monthly = monthly_revenue(sales)
    assert monthly["Revenue"].tolist() == [30.0, 5.0]


def test_product_recommender_returns_co_occurring_product():
    baskets = pd.DataFrame({"Items": ['["A", "B"]', '["A", "C"]', '["A", "B"]']})
    recommender = ProductRecommender(baskets)
    result = recommender.recommend("A")
    assert result.iloc[0]["StockCode"] == "B"
    assert int(result.iloc[0]["CoOccurrences"]) == 2


def test_product_recommender_normalizes_product_codes():
    baskets = pd.DataFrame({"Items": ['[" A ", " B "]', '["A", "C"]']})
    recommender = ProductRecommender(baskets)
    result = recommender.recommend(" a ")
    assert set(result["StockCode"]) == {"B", "C"}


def test_product_recommender_counts_each_product_once_per_basket():
    baskets = pd.DataFrame({"Items": ['["A", "A", "B"]', '["A", "B"]']})
    result = ProductRecommender(baskets).recommend("A")
    counts = result.set_index("StockCode")["CoOccurrences"]
    assert counts["B"] == 2
    assert "A" not in counts.index


def test_customer_segmentation_returns_expected_segment_column():
    rfm = pd.DataFrame({
        "Customer ID": range(1, 11),
        "RecencyDays": [5, 10, 20, 30, 40, 50, 60, 70, 80, 90],
        "Frequency": [10, 9, 8, 7, 6, 5, 4, 3, 2, 1],
        "Monetary": [1000, 900, 800, 700, 600, 500, 400, 300, 200, 100],
    })
    segmented, model = segment_customers(rfm, cluster_count=3)
    assert len(segmented) == 10
    assert "Segment" in segmented.columns
    assert model.n_clusters == 3


def test_numeric_summary_ignores_text_columns():
    frame = pd.DataFrame({
        "Invoice": ["1", "2"],
        "ItemCount": [2, 5],
        "TotalRevenue": [10.0, 25.0],
    })
    summary = numeric_summary(frame)
    assert "ItemCount" in summary.columns
    assert "TotalRevenue" in summary.columns
    assert "Invoice" not in summary.columns


def test_monthly_revenue_drops_unparseable_dates():
    sales = pd.DataFrame({
        "Invoice": ["1", "2"],
        "InvoiceDate": ["2024-01-15", "not-a-date"],
        "Revenue": [12.5, 1000.0],
    })
    result = monthly_revenue(sales)
    assert result[["Month", "Revenue", "Orders"]].to_dict("records") == [
        {"Month": "2024-01", "Revenue": 12.5, "Orders": 1}
    ]


def test_top_products_and_country_revenue_are_ranked():
    sales = pd.DataFrame({
        "StockCode": ["A", "B", "A"],
        "Description": ["Alpha", "Beta", "Alpha"],
        "Quantity": [1, 4, 2],
        "Revenue": [10.0, 20.0, 30.0],
        "Invoice": ["1", "1", "2"],
        "Country": ["X", "Y", "X"],
    })
    assert top_products(sales, limit=1).iloc[0]["StockCode"] == "A"
    assert revenue_by_country(sales, limit=1).iloc[0]["Country"] == "X"


def test_recommender_counts_each_item_once_per_invoice():
    baskets = pd.DataFrame({
        "Items": ['["A", "A", "B"]', '["A", "B"]', '["A", "C"]']
    })
    recommender = ProductRecommender(baskets)
    result = recommender.recommend("A")
    assert int(result.loc[result["StockCode"].eq("B"), "CoOccurrences"].iloc[0]) == 2
    assert not result["StockCode"].eq("A").any()


def test_uploaded_dashboard_datasets_are_loaded_and_validated():
    upload_files = {
        "eligible_sales.csv": (
            b"Invoice,StockCode,Description,InvoiceDate,Revenue,Quantity,Customer ID,Country\n"
            b"1,A,Alpha,2024-01-01,10,1,7,UK\n"
        ),
        "customer_rfm.csv": (
            b"Customer ID,RecencyDays,Frequency,Monetary\n7,2,1,10\n"
        ),
        "market_basket_transactions.csv": (
            b"Invoice,Items,ItemCount\n1,\"[\"\"A\"\"]\",1\n"
        ),
    }
    sales, rfm, baskets = load_uploaded_datasets(upload_files)
    assert sales.iloc[0]["StockCode"] == "A"
    assert rfm.iloc[0]["Customer ID"] == "7"
    assert int(baskets.iloc[0]["ItemCount"]) == 1


def test_uploaded_dashboard_datasets_report_missing_files():
    try:
        load_uploaded_datasets({})
    except ValueError as exc:
        assert "eligible_sales.csv" in str(exc)
    else:
        raise AssertionError("Missing uploads should be rejected.")
