"""Crawler agent implementation."""

from ecomscout_ai.crawlers.factory import get_crawler_provider
from ecomscout_ai.state.agent_state import AgentState


def crawler_agent(state: AgentState) -> dict:
    """Fetch product data using the crawler provider selected by research output."""
    provider = get_crawler_provider("amazon")
    crawl_result = provider.fetch_products(
        keyword=state["crawl_keyword"],
        fields=state["crawl_fields"],
        depth=state["crawl_depth"],
        limit=state["crawl_limit"],
    )
    return {
        "products": crawl_result["products"],
        "crawl_status": crawl_result["crawl_status"],
    }
