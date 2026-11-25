from __future__ import annotations

import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


def segment_customers(rfm: pd.DataFrame, cluster_count: int = 5) -> tuple[pd.DataFrame, KMeans]:
    required = {"Customer ID", "RecencyDays", "Frequency", "Monetary"}
    missing = sorted(required.difference(rfm.columns))
    if missing:
        raise ValueError("RFM data is missing columns: " + ", ".join(missing))

    result = rfm.dropna(subset=["RecencyDays", "Frequency", "Monetary"]).copy()
    if len(result) < cluster_count:
        raise ValueError(
            f"Need at least {cluster_count} customers for segmentation; found {len(result)}."
        )

    features = result[["RecencyDays", "Frequency", "Monetary"]]
    scaled = StandardScaler().fit_transform(features)
    model = KMeans(n_clusters=cluster_count, random_state=42, n_init=10)
    result["SegmentCode"] = model.fit_predict(scaled)

    summary = result.groupby("SegmentCode").agg(
        Recency=("RecencyDays", "mean"),
        Frequency=("Frequency", "mean"),
        Monetary=("Monetary", "mean"),
    )
    recency_rank = summary["Recency"].rank(method="dense", ascending=True)
    frequency_rank = summary["Frequency"].rank(method="dense", ascending=True)
    monetary_rank = summary["Monetary"].rank(method="dense", ascending=True)

    def segment_name(code: int) -> str:
        recency = recency_rank.loc[code]
        frequency = frequency_rank.loc[code]
        monetary = monetary_rank.loc[code]
        if recency == 1 and frequency == len(summary) and monetary == len(summary):
            return "Champions"
        if recency >= max(2, len(summary) - 1) and frequency <= 2:
            return "At Risk"
        if frequency == len(summary):
            return "Loyal Customers"
        if monetary == len(summary):
            return "High Value"
        if recency == 1:
            return "Recent Customers"
        return "Needs Attention"

    names = {code: segment_name(code) for code in summary.index}
    result["Segment"] = result["SegmentCode"].map(names)
    return result, model
