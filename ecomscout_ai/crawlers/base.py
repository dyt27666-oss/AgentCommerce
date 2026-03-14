"""Base definitions for crawler providers."""

from typing import Protocol


class CrawlerProvider(Protocol):
    """Protocol implemented by concrete crawler providers."""

    def fetch_products(
        self,
        keyword: str,
        fields: list[str],
        depth: int,
        limit: int,
    ) -> dict:
        """Fetch normalized product data and crawl status for the request."""
