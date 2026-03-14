"""Unit tests for the analysis agent."""

from ecomscout_ai.agents.analysis_agent import analysis_agent


def test_analysis_agent_computes_richer_market_analytics() -> None:
    """The analysis agent should calculate richer price, review, brand, and quality metrics."""
    state = {
        "clean_data": [
            {
                "name": "Earphone A",
                "price": 99.0,
                "rating": 4.7,
                "reviews": 3200,
                "url": "https://example.com/a",
                "brand": "SoundMax",
                "bsr": "#120",
                "category": "Earbuds",
            },
            {
                "name": "Earphone B",
                "price": 199.0,
                "rating": 4.5,
                "reviews": 1800,
                "url": "https://example.com/b",
                "brand": "SoundMax",
                "bsr": "#240",
                "category": "Earbuds",
            },
            {
                "name": "Earphone C",
                "price": 299.0,
                "rating": None,
                "reviews": 2400,
                "url": "https://example.com/c",
                "brand": "AudioNova",
                "bsr": None,
                "category": "Headphones",
            },
            {
                "name": "Earphone D",
                "price": 399.0,
                "rating": 4.8,
                "reviews": None,
                "url": "https://example.com/d",
                "brand": None,
                "bsr": None,
                "category": None,
            },
        ]
    }

    result = analysis_agent(state)
    analysis = result["analysis_result"]

    assert analysis["product_count"] == 4
    assert analysis["price_analysis"]["avg_price"] == 249.0
    assert analysis["price_analysis"]["median_price"] == 249.0
    assert analysis["price_analysis"]["price_percentiles"] == {
        "p25": 174.0,
        "p50": 249.0,
        "p75": 324.0,
    }
    assert analysis["price_analysis"]["price_bands"] == {
        "low": 1,
        "mid": 2,
        "high": 1,
    }
    assert analysis["review_analysis"]["review_avg"] == 2466.67
    assert analysis["review_analysis"]["review_median"] == 2400.0
    assert analysis["review_analysis"]["review_distribution"] == {
        "0-999": 0,
        "1000-2999": 2,
        "3000+": 1,
    }
    assert analysis["brand_analysis"]["brand_counts"] == {
        "SoundMax": 2,
        "AudioNova": 1,
    }
    assert analysis["brand_analysis"]["brand_share"] == {
        "SoundMax": 0.5,
        "AudioNova": 0.25,
    }
    assert analysis["brand_analysis"]["brand_coverage"] == "medium"
    assert analysis["dataset_quality"] == {
        "sample_size": 4,
        "missing_price_ratio": 0.0,
        "missing_rating_ratio": 0.25,
        "missing_brand_ratio": 0.25,
    }
    assert analysis["rating_distribution"] == {
        "4.5": 1,
        "4.7": 1,
        "4.8": 1,
    }


def test_analysis_agent_returns_empty_defaults_when_no_valid_data() -> None:
    """The analysis agent should return a complete empty structure for empty input."""
    result = analysis_agent({"clean_data": []})

    assert result["analysis_result"] == {
        "product_count": 0,
        "price_analysis": {
            "avg_price": 0.0,
            "median_price": 0.0,
            "price_percentiles": {"p25": 0.0, "p50": 0.0, "p75": 0.0},
            "price_bands": {"low": 0, "mid": 0, "high": 0},
        },
        "review_analysis": {
            "review_avg": 0.0,
            "review_median": 0.0,
            "review_distribution": {"0-999": 0, "1000-2999": 0, "3000+": 0},
        },
        "brand_analysis": {
            "brand_counts": {},
            "brand_share": {},
            "brand_coverage": "low",
        },
        "dataset_quality": {
            "sample_size": 0,
            "missing_price_ratio": 0.0,
            "missing_rating_ratio": 0.0,
            "missing_brand_ratio": 0.0,
        },
        "rating_distribution": {},
    }
