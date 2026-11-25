from __future__ import annotations

import json
from collections import defaultdict
from itertools import combinations

import pandas as pd


class ProductRecommender:
    def __init__(self, baskets: pd.DataFrame) -> None:
        self.baskets = baskets
        self._co_counts: dict[tuple[str, str], int] = defaultdict(int)
        self._item_counts: dict[str, int] = defaultdict(int)
        self._descriptions: dict[str, str] = {}
        self._fit()

    def _fit(self) -> None:
        for row in self.baskets.itertuples(index=False):
            raw_items = getattr(row, "Items", "[]")
            try:
                items = json.loads(raw_items) if isinstance(raw_items, str) else list(raw_items)
            except (json.JSONDecodeError, TypeError):
                items = []
            unique_items = sorted(
                set(
                    str(item).strip().upper()
                    for item in items
                    if str(item).strip()
                )
            )
            for item in unique_items:
                self._item_counts[item] += 1
            for left, right in combinations(unique_items, 2):
                pair = tuple(sorted((left, right)))
                self._co_counts[pair] += 1

    def recommend(self, stock_code: str, limit: int = 5) -> pd.DataFrame:
        stock_code = str(stock_code).strip().upper()
        scores: dict[str, int] = defaultdict(int)
        for pair, count in self._co_counts.items():
            if stock_code in pair:
                partner = pair[1] if pair[0] == stock_code else pair[0]
                scores[partner] += count
        recommendations = [
            {"StockCode": code, "CoOccurrences": count}
            for code, count in sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        ]
        return pd.DataFrame(recommendations).head(limit)

    def popular_products(self, limit: int = 10) -> pd.DataFrame:
        products = [
            {"StockCode": code, "BasketCount": count}
            for code, count in sorted(
                self._item_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ]
        return pd.DataFrame(products).head(limit)
