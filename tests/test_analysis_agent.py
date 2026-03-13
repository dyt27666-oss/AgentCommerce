"""Unit tests for the analysis agent."""

from ecomscout_ai.agents.analysis_agent import analysis_agent


def test_analysis_agent_computes_price_statistics() -> None:
    """The analysis agent should calculate average, minimum, and maximum price."""
    state = {
        "clean_data": [
            {"name": "Earphone A", "price": 199, "rating": 4.7, "reviews": 3200},
            {"name": "Earphone B", "price": 249, "rating": 4.5, "reviews": 1800},
            {"name": "Earphone C", "price": 299, "rating": 4.6, "reviews": 2400},
        ]
    }

    result = analysis_agent(state)

    assert result["analysis_result"]["average_price"] == 249.0
    assert result["analysis_result"]["max_price"] == 299
    assert result["analysis_result"]["min_price"] == 199


def test_analysis_agent_returns_empty_defaults_when_no_valid_data() -> None:
    """The analysis agent should return a complete empty structure for empty input."""
    result = analysis_agent({"clean_data": []})

    assert result["analysis_result"] == {
        "average_price": 0,
        "max_price": 0,
        "min_price": 0,
        "product_count": 0,
    }
