"""Unit tests for the analysis agent."""

from ecomscout_ai.agents.analysis_agent import analysis_agent


def test_analysis_agent_computes_price_statistics() -> None:
    """The analysis agent should calculate summary statistics from product prices."""
    state = {
        "clean_data": [
            {"name": "Earphone A", "price": 199, "rating": 4.7, "reviews": 3200},
            {"name": "Earphone B", "price": 249, "rating": 4.5, "reviews": 1800},
            {"name": "Earphone C", "price": 299, "rating": 4.6, "reviews": 2400},
        ]
    }

    result = analysis_agent(state)

    assert result["analysis_result"]["product_count"] == 3
    assert result["analysis_result"]["avg_price"] == 249.0
    assert result["analysis_result"]["price_range"] == {"min": 199.0, "max": 299.0}
    assert result["analysis_result"]["rating_distribution"] == {
        "4.5": 1,
        "4.6": 1,
        "4.7": 1,
    }


def test_analysis_agent_returns_empty_defaults_when_no_valid_data() -> None:
    """The analysis agent should return a complete empty structure for empty input."""
    result = analysis_agent({"clean_data": []})

    assert result["analysis_result"] == {
        "product_count": 0,
        "avg_price": 0.0,
        "price_range": {"min": 0.0, "max": 0.0},
        "rating_distribution": {},
    }
