from __future__ import annotations

import json
from collections import defaultdict

import pandas as pd


class ProductRecommender:
    def __init__(self, baskets: pd.DataFrame) -> None:
        self.baskets = baskets
        self._items_by_basket: list[tuple[str, ...]] = []
        self._basket_indices_by_item: dict[str, list[int]] = defaultdict(list)
        self._item_counts: dict[str, int] = defaultdict(int)
        self._fit()

    def _fit(self) -> None:
        for row in self.baskets.itertuples(index=False):
            raw_items = getattr(row, "Items", "[]")
            try:
                items = json.loads(raw_items) if isinstance(raw_items, str) else list(raw_items)
            except (json.JSONDecodeError, TypeError):
                items = []
            unique_items = tuple(
                sorted(
                    set(
                        str(item).strip().upper()
                        for item in items
                        if str(item).strip()
                    )
                )
            )
            basket_index = len(self._items_by_basket)
            self._items_by_basket.append(unique_items)
            for item in unique_items:
                self._item_counts[item] += 1
                self._basket_indices_by_item[item].append(basket_index)

    def recommend(self, stock_code: str, limit: int = 5) -> pd.DataFrame:
        stock_code = str(stock_code).strip().upper()
        scores: dict[str, int] = defaultdict(int)
        for basket_index in self._basket_indices_by_item.get(stock_code, ()):
            for partner in self._items_by_basket[basket_index]:
                if partner != stock_code:
                    scores[partner] += 1
        recommendations = [
            {"StockCode": code, "CoOccurrences": count}
            for code, count in sorted(
                scores.items(), key=lambda item: (-item[1], item[0])
            )[:limit]
        ]
        return pd.DataFrame(recommendations)

    def popular_products(self, limit: int = 10) -> pd.DataFrame:
        products = [
            {"StockCode": code, "BasketCount": count}
            for code, count in sorted(
                self._item_counts.items(), key=lambda item: (-item[1], item[0])
            )
        ]
        return pd.DataFrame(products).head(limit)
