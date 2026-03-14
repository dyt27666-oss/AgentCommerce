"""Common helpers for analysis modules."""

from __future__ import annotations

from math import ceil, floor


def round_float(value: float) -> float:
    """Round a numeric value to two decimals."""
    return round(float(value), 2)


def percentile(values: list[float], ratio: float) -> float:
    """Calculate a linear-interpolated percentile for a numeric list."""
    if not values:
        return 0.0
    sorted_values = sorted(float(value) for value in values)
    if len(sorted_values) == 1:
        return round_float(sorted_values[0])
    position = (len(sorted_values) - 1) * ratio
    lower = floor(position)
    upper = ceil(position)
    if lower == upper:
        return round_float(sorted_values[lower])
    interpolated = sorted_values[lower] + (
        sorted_values[upper] - sorted_values[lower]
    ) * (position - lower)
    return round_float(interpolated)


def median(values: list[float]) -> float:
    """Return the median value for a numeric list."""
    return percentile(values, 0.5)
