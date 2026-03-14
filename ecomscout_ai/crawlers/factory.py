"""Factory for crawler providers."""

from ecomscout_ai.crawlers.base import CrawlerProvider
from ecomscout_ai.crawlers.providers.amazon_provider import AmazonProvider


def get_crawler_provider(target: str) -> CrawlerProvider:
    """Return a crawler provider for the requested target."""
    if target.lower() == "amazon":
        return AmazonProvider()
    raise ValueError(f"Unsupported crawl target: {target}")
