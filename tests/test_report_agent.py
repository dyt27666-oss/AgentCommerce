"""Unit tests for report data source visibility."""

from ecomscout_ai.agents.report_agent import report_agent


def test_report_agent_shows_crawl_status_and_error_metadata() -> None:
    """The report should expose crawl status, data origin, and error metadata."""
    result = report_agent(
        {
            "user_query": "Analyze bluetooth earphone market",
            "crawl_keyword": "bluetooth earphone",
            "crawl_fields": ["name", "price", "rating", "reviews", "url"],
            "crawl_depth": 1,
            "crawl_limit": 20,
            "crawl_status": "fallback",
            "crawl_warnings": ["detail_fetch_failed"],
            "crawl_error_type": "blocked_page",
            "fallback_used": True,
            "products": [{"name": "A", "price": 100.0, "rating": 4.5, "reviews": 100, "url": "https://example.com/a"}],
            "clean_data": [{"name": "A", "price": 100.0, "rating": 4.5, "reviews": 100, "url": "https://example.com/a"}],
            "analysis_result": {
                "product_count": 1,
                "price_analysis": {
                    "avg_price": 100.0,
                    "median_price": 100.0,
                    "price_percentiles": {"p25": 100.0, "p50": 100.0, "p75": 100.0},
                    "price_bands": {"low": 0, "mid": 1, "high": 0},
                },
                "review_analysis": {
                    "review_avg": 100.0,
                    "review_median": 100.0,
                    "review_distribution": {"0-999": 1, "1000-2999": 0, "3000+": 0},
                },
                "brand_analysis": {
                    "brand_counts": {},
                    "brand_share": {},
                    "brand_coverage": "low",
                },
                "dataset_quality": {
                    "sample_size": 1,
                    "missing_price_ratio": 0.0,
                    "missing_rating_ratio": 0.0,
                    "missing_brand_ratio": 1.0,
                },
                "rating_distribution": {"4.5": 1},
            },
            "strategy_mode": "rule_based",
            "strategy_execution_mode": "rule_based_fallback",
            "llm_parse_status": "fallback",
            "llm_fallback_reason": "schema_validation_failed",
            "decision_brief": {
                "market_summary": "Sample is fallback-based and limited.",
                "pricing_recommendation": "Use a cautious launch price.",
                "key_risks": ["Fallback data may not reflect live Amazon conditions."],
                "next_actions": ["Validate with a successful live crawl."],
                "confidence": "low",
            },
            "strategy": "Use a cautious launch price.",
            "report": "",
        }
    )

    report = result["report"]
    assert "crawler_status: fallback" in report
    assert "data_origin: mock_dataset" in report
    assert "error_type: blocked_page" in report
    assert "fallback_used: True" in report
    assert "warnings: detail_fetch_failed" in report
    assert "## Decision Brief" in report
    assert "confidence: low" in report
    assert "llm_parse_status: fallback" in report
    assert "llm_fallback_reason: schema_validation_failed" in report
