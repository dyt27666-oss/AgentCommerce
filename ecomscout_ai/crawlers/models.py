"""Shared crawler data models."""

from dataclasses import dataclass, asdict


@dataclass
class ProductRecord:
    """Normalized product structure used across the workflow."""

    name: str
    price: float
    rating: float | None
    reviews: int | None
    url: str
    brand: str | None = None
    bsr: str | None = None
    category: str | None = None

    def to_dict(self) -> dict:
        """Convert the record into a plain dictionary."""
        return asdict(self)
