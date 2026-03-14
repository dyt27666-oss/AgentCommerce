"""Brand analytics module."""

from __future__ import annotations


def analyze_brands(records: list[dict]) -> dict:
    """Compute brand counts, share, and coverage score."""
    sample_size = len(records)
    brand_counts: dict[str, int] = {}

    for record in records:
        if not isinstance(record, dict):
            continue
        brand = record.get("brand")
        if isinstance(brand, str) and brand.strip():
            normalized = brand.strip()
            brand_counts[normalized] = brand_counts.get(normalized, 0) + 1

    brand_share = {
        brand: round(count / sample_size, 2) if sample_size else 0.0
        for brand, count in brand_counts.items()
    }
    coverage_ratio = round(sum(brand_counts.values()) / sample_size, 2) if sample_size else 0.0

    if coverage_ratio >= 0.9:
        brand_coverage = "high"
    elif coverage_ratio >= 0.4:
        brand_coverage = "medium"
    else:
        brand_coverage = "low"

    return {
        "brand_counts": brand_counts,
        "brand_share": brand_share,
        "brand_coverage": brand_coverage,
    }
