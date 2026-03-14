"""Dataset quality metrics module."""

from __future__ import annotations


def analyze_quality(records: list[dict]) -> dict:
    """Compute simple dataset quality metrics."""
    sample_size = len(records)
    if sample_size == 0:
        return {
            "sample_size": 0,
            "missing_price_ratio": 0.0,
            "missing_rating_ratio": 0.0,
            "missing_brand_ratio": 0.0,
        }

    missing_price = 0
    missing_rating = 0
    missing_brand = 0
    for record in records:
        if record.get("price") is None:
            missing_price += 1
        if record.get("rating") is None:
            missing_rating += 1
        brand = record.get("brand")
        if brand is None or (isinstance(brand, str) and not brand.strip()):
            missing_brand += 1

    return {
        "sample_size": sample_size,
        "missing_price_ratio": round(missing_price / sample_size, 2),
        "missing_rating_ratio": round(missing_rating / sample_size, 2),
        "missing_brand_ratio": round(missing_brand / sample_size, 2),
    }
