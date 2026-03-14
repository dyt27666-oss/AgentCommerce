"""Price analytics module."""

from __future__ import annotations

from ecomscout_ai.analysis.common import median, percentile, round_float


def analyze_prices(records: list[dict]) -> dict:
    """Compute averages, median, percentiles, and percentile-based price bands."""
    prices = [
        float(record["price"])
        for record in records
        if isinstance(record, dict) and isinstance(record.get("price"), (int, float))
    ]

    if not prices:
        return {
            "avg_price": 0.0,
            "median_price": 0.0,
            "price_percentiles": {"p25": 0.0, "p50": 0.0, "p75": 0.0},
            "price_bands": {"low": 0, "mid": 0, "high": 0},
        }

    p25 = percentile(prices, 0.25)
    p50 = median(prices)
    p75 = percentile(prices, 0.75)

    price_bands = {"low": 0, "mid": 0, "high": 0}
    for price in prices:
        if price < p25:
            price_bands["low"] += 1
        elif price > p75:
            price_bands["high"] += 1
        else:
            price_bands["mid"] += 1

    return {
        "avg_price": round_float(sum(prices) / len(prices)),
        "median_price": p50,
        "price_percentiles": {"p25": p25, "p50": p50, "p75": p75},
        "price_bands": price_bands,
    }
