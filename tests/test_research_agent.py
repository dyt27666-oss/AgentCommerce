"""Unit tests for the research agent."""

from ecomscout_ai.agents.research_agent import research_agent


def make_state(user_query: str) -> dict:
    """Create the minimum state needed by the research agent."""
    return {
        "user_query": user_query,
        "crawl_keyword": "",
        "crawl_fields": [],
        "crawl_depth": 1,
        "crawl_limit": 20,
        "crawl_status": "failed",
        "products": [],
        "clean_data": [],
        "analysis_result": {},
        "strategy": "",
        "report": "",
    }


def test_research_agent_extracts_default_crawl_settings() -> None:
    """The research agent should derive search-page defaults from a normal query."""
    result = research_agent(make_state("Analyze bluetooth earphone market"))

    assert result["crawl_keyword"] == "bluetooth earphone"
    assert result["crawl_depth"] == 1
    assert result["crawl_limit"] == 20
    assert result["crawl_fields"] == ["name", "price", "rating", "reviews", "url"]


def test_research_agent_expands_fields_for_detail_requests() -> None:
    """The research agent should request detail fields when the query asks for them."""
    result = research_agent(
        make_state("Research bluetooth earphone market with brand bsr and category details")
    )

    assert result["crawl_depth"] == 2
    assert result["crawl_fields"] == [
        "name",
        "price",
        "rating",
        "reviews",
        "url",
        "brand",
        "bsr",
        "category",
    ]
