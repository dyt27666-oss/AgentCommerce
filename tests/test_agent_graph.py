"""Integration tests for the EcomScout-AI LangGraph workflow."""

from ecomscout_ai.graph.agent_graph import build_agent_graph


def make_initial_state() -> dict:
    """Build the initial state used by the workflow tests."""
    return {
        "user_query": "Analyze bluetooth earphone market",
        "crawl_keyword": "",
        "crawl_fields": [],
        "crawl_depth": 1,
        "crawl_limit": 20,
        "crawl_status": "failed",
        "crawl_warnings": [],
        "crawl_error_type": None,
        "fallback_used": False,
        "products": [],
        "clean_data": [],
        "analysis_result": {},
        "strategy_mode": "rule_based",
        "strategy_execution_mode": "rule_based",
        "decision_brief": {
            "market_summary": "",
            "pricing_recommendation": "",
            "key_risks": [],
            "next_actions": [],
            "confidence": "low",
        },
        "strategy": "",
        "report": "",
    }


def test_agent_graph_runs_end_to_end() -> None:
    """The compiled graph should produce every expected output field."""
    graph = build_agent_graph()

    result = graph.invoke(make_initial_state())

    assert result["crawl_keyword"] == "bluetooth earphone"
    assert result["crawl_fields"] == ["name", "price", "rating", "reviews", "url"]
    assert result["crawl_depth"] == 1
    assert result["crawl_limit"] == 20
    assert result["crawl_status"] in {"success", "partial_success", "fallback"}
    assert "crawl_warnings" in result
    assert "crawl_error_type" in result
    assert "fallback_used" in result
    assert result["products"]
    assert result["clean_data"]
    assert result["analysis_result"]
    assert result["analysis_result"]["product_count"] >= 1
    assert "price_analysis" in result["analysis_result"]
    assert "review_analysis" in result["analysis_result"]
    assert "brand_analysis" in result["analysis_result"]
    assert "dataset_quality" in result["analysis_result"]
    assert result["strategy"]
    assert result["strategy_execution_mode"] in {
        "rule_based",
        "llm_assisted",
        "rule_based_fallback",
    }
    assert result["decision_brief"]["confidence"] in {"high", "medium", "low"}
    assert result["report"]


def test_final_report_contains_required_sections() -> None:
    """The generated report should include the required Markdown sections."""
    graph = build_agent_graph()

    result = graph.invoke(make_initial_state())
    report = result["report"]

    assert report.startswith("# Market Analysis Report")
    assert "## Query" in report
    assert "## Crawl Configuration" in report
    assert "## Data Source" in report
    assert "crawler_status:" in report
    assert "data_origin:" in report
    assert "## Dataset Summary" in report
    assert "## Dataset Quality" in report
    assert "## Price Analysis" in report
    assert "## Price Distribution" in report
    assert "## Review Statistics" in report
    assert "## Brand Overview" in report
    assert "## Strategy Suggestion" in report
    assert "## Decision Brief" in report
