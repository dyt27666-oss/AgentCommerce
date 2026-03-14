"""Unit tests for crawler agent status handling."""

from ecomscout_ai.agents.crawler_agent import crawler_agent


class FakeProvider:
    """Provider stub returning a predetermined result."""

    def __init__(self, result: dict):
        self.result = result

    def fetch_products(self, keyword: str, fields: list[str], depth: int, limit: int) -> dict:
        return self.result


def test_crawler_agent_returns_products_and_status(monkeypatch) -> None:
    """Crawler agent should forward provider status and products into state updates."""
    monkeypatch.setattr(
        "ecomscout_ai.agents.crawler_agent.get_crawler_provider",
        lambda target: FakeProvider(
            {
                "products": [
                    {
                        "name": "Product A",
                        "price": 10.0,
                        "rating": 4.5,
                        "reviews": 100,
                        "url": "https://example.com/a",
                    }
                ],
                "crawl_status": "success",
            }
        ),
    )

    result = crawler_agent(
        {
            "user_query": "query",
            "crawl_keyword": "keyword",
            "crawl_fields": ["name", "price", "rating", "reviews", "url"],
            "crawl_depth": 1,
            "crawl_limit": 20,
            "crawl_status": "failed",
            "products": [],
            "clean_data": [],
            "analysis_result": {},
            "strategy": "",
            "report": "",
        }
    )

    assert result["crawl_status"] == "success"
    assert result["products"][0]["name"] == "Product A"
