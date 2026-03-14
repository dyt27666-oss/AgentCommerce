"""Review analytics module."""

from __future__ import annotations

from ecomscout_ai.analysis.common import median, round_float


def analyze_reviews(records: list[dict]) -> dict:
    """Compute review count aggregates and coarse bucket distribution."""
    reviews = [
        float(record["reviews"])
        for record in records
        if isinstance(record, dict) and isinstance(record.get("reviews"), int)
    ]

    distribution = {"0-999": 0, "1000-2999": 0, "3000+": 0}
    for count in reviews:
        if count < 1000:
            distribution["0-999"] += 1
        elif count < 3000:
            distribution["1000-2999"] += 1
        else:
            distribution["3000+"] += 1

    if not reviews:
        return {
            "review_avg": 0.0,
            "review_median": 0.0,
            "review_distribution": distribution,
        }

    return {
        "review_avg": round_float(sum(reviews) / len(reviews)),
        "review_median": median(reviews),
        "review_distribution": distribution,
    }
