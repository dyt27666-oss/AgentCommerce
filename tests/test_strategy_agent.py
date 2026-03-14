"""Unit tests for strategy agent modes and decision brief output."""

from ecomscout_ai.agents.strategy_agent import (
    LLM_PARSE_STATUS_FALLBACK,
    LLM_PARSE_STATUS_NOT_ATTEMPTED,
    LLM_PARSE_STATUS_PARSED,
    STRATEGY_MODE_LLM_ASSISTED,
    STRATEGY_MODE_RULE_BASED,
    STRATEGY_MODE_RULE_BASED_FALLBACK,
    DEFAULT_DECISION_BRIEF,
    _extract_json_object,
    strategy_agent,
)


def make_state(strategy_mode: str) -> dict:
    """Create a minimal state for strategy agent tests."""
    return {
        "user_query": "Analyze bluetooth earphone market",
        "crawl_keyword": "bluetooth earphone",
        "crawl_fields": ["name", "price", "rating", "reviews", "url"],
        "crawl_depth": 1,
        "crawl_limit": 20,
        "crawl_status": "fallback",
        "crawl_warnings": [],
        "crawl_error_type": "network_error",
        "fallback_used": True,
        "products": [],
        "clean_data": [],
        "analysis_result": {
            "product_count": 3,
            "price_analysis": {
                "avg_price": 249.0,
                "median_price": 249.0,
                "price_percentiles": {"p25": 224.0, "p50": 249.0, "p75": 274.0},
                "price_bands": {"low": 1, "mid": 1, "high": 1},
            },
            "review_analysis": {
                "review_avg": 3050.33,
                "review_median": 3201.0,
                "review_distribution": {"0-999": 0, "1000-2999": 1, "3000+": 2},
            },
            "brand_analysis": {
                "brand_counts": {},
                "brand_share": {},
                "brand_coverage": "low",
            },
            "dataset_quality": {
                "sample_size": 3,
                "missing_price_ratio": 0.0,
                "missing_rating_ratio": 0.0,
                "missing_brand_ratio": 1.0,
            },
            "rating_distribution": {"4.4": 1, "4.6": 1, "4.7": 1},
        },
        "strategy_mode": strategy_mode,
        "strategy_execution_mode": STRATEGY_MODE_RULE_BASED,
        "llm_parse_status": LLM_PARSE_STATUS_NOT_ATTEMPTED,
        "llm_fallback_reason": None,
        "decision_brief": DEFAULT_DECISION_BRIEF.copy(),
        "strategy": "",
        "report": "",
    }


def test_strategy_agent_rule_based_returns_structured_brief() -> None:
    """Rule-based mode should return strategy text plus a structured decision brief."""
    result = strategy_agent(make_state(STRATEGY_MODE_RULE_BASED))

    assert result["strategy_execution_mode"] == STRATEGY_MODE_RULE_BASED
    assert result["strategy"]
    assert result["decision_brief"]["market_summary"]
    assert result["decision_brief"]["pricing_recommendation"]
    assert isinstance(result["decision_brief"]["key_risks"], list)
    assert isinstance(result["decision_brief"]["next_actions"], list)
    assert result["decision_brief"]["confidence"] in {"high", "medium", "low"}
    assert result["llm_parse_status"] == LLM_PARSE_STATUS_NOT_ATTEMPTED
    assert result["llm_fallback_reason"] is None


def test_strategy_agent_llm_assisted_falls_back_when_llm_errors(monkeypatch) -> None:
    """LLM-assisted mode should fall back honestly when the model call fails."""
    monkeypatch.setattr(
        "ecomscout_ai.agents.strategy_agent._run_llm_assisted_strategy",
        lambda state: (_ for _ in ()).throw(RuntimeError("llm failed")),
    )

    result = strategy_agent(make_state(STRATEGY_MODE_LLM_ASSISTED))

    assert result["strategy_execution_mode"] == STRATEGY_MODE_RULE_BASED_FALLBACK
    assert result["strategy"]
    assert result["decision_brief"]["confidence"] in {"high", "medium", "low"}
    assert result["llm_parse_status"] == LLM_PARSE_STATUS_FALLBACK
    assert result["llm_fallback_reason"] == "llm_runtime_error"


def test_strategy_agent_llm_assisted_accepts_valid_json_object(monkeypatch) -> None:
    """LLM-assisted mode should accept a valid brief and persist diagnostics honestly."""
    monkeypatch.setattr(
        "ecomscout_ai.agents.strategy_agent._run_llm_assisted_strategy",
        lambda state: {
            "strategy": "Use a premium launch position.",
            "decision_brief": {
                "market_summary": "Competition is mid-priced.",
                "pricing_recommendation": "Launch slightly above the median.",
                "key_risks": ["Fallback data reduces confidence."],
                "next_actions": ["Validate with live crawl data."],
                "confidence": "medium",
            },
        },
    )

    result = strategy_agent(make_state(STRATEGY_MODE_LLM_ASSISTED))

    assert result["strategy_execution_mode"] == STRATEGY_MODE_LLM_ASSISTED
    assert result["strategy"] == "Use a premium launch position."
    assert result["llm_parse_status"] == LLM_PARSE_STATUS_PARSED
    assert result["llm_fallback_reason"] is None
    assert result["decision_brief"] == {
        "market_summary": "Competition is mid-priced.",
        "pricing_recommendation": "Launch slightly above the median.",
        "key_risks": ["Fallback data reduces confidence."],
        "next_actions": ["Validate with live crawl data."],
        "confidence": "medium",
    }


def test_extract_json_object_accepts_markdown_wrapped_json() -> None:
    """Markdown fenced JSON should still be extracted before validation."""
    response = """```json
    {
      "market_summary": "Demand is clustered in the mid band.",
      "pricing_recommendation": "Enter near the current median.",
      "key_risks": ["Fallback data weakens confidence."],
      "next_actions": ["Re-run with live crawl data."],
      "confidence": "medium"
    }
    ```"""

    parsed = _extract_json_object(response)

    assert parsed["confidence"] == "medium"


def test_strategy_agent_llm_assisted_falls_back_on_missing_fields(monkeypatch) -> None:
    """Missing required brief fields should trigger a rule-based fallback."""
    monkeypatch.setattr(
        "ecomscout_ai.agents.strategy_agent._run_llm_assisted_strategy",
        lambda state: {
            "strategy": "Incomplete result",
            "decision_brief": {
                "market_summary": "Only one field present.",
                "confidence": "medium",
            },
        },
    )

    result = strategy_agent(make_state(STRATEGY_MODE_LLM_ASSISTED))

    assert result["strategy_execution_mode"] == STRATEGY_MODE_RULE_BASED_FALLBACK
    assert result["llm_parse_status"] == LLM_PARSE_STATUS_FALLBACK
    assert result["llm_fallback_reason"] == "schema_validation_failed"


def test_strategy_agent_llm_assisted_falls_back_on_invalid_confidence(monkeypatch) -> None:
    """An unsupported confidence value should be rejected rather than normalized silently."""
    monkeypatch.setattr(
        "ecomscout_ai.agents.strategy_agent._run_llm_assisted_strategy",
        lambda state: {
            "strategy": "Use the premium band.",
            "decision_brief": {
                "market_summary": "Competition is mid-priced.",
                "pricing_recommendation": "Launch above the median.",
                "key_risks": ["Low data quality."],
                "next_actions": ["Retry with live data."],
                "confidence": "certain",
            },
        },
    )

    result = strategy_agent(make_state(STRATEGY_MODE_LLM_ASSISTED))

    assert result["strategy_execution_mode"] == STRATEGY_MODE_RULE_BASED_FALLBACK
    assert result["llm_fallback_reason"] == "schema_validation_failed"


def test_strategy_agent_llm_assisted_falls_back_on_invalid_list_type(monkeypatch) -> None:
    """List fields must remain typed lists of strings."""
    monkeypatch.setattr(
        "ecomscout_ai.agents.strategy_agent._run_llm_assisted_strategy",
        lambda state: {
            "strategy": "Use the premium band.",
            "decision_brief": {
                "market_summary": "Competition is mid-priced.",
                "pricing_recommendation": "Launch above the median.",
                "key_risks": {"risk": "Low data quality."},
                "next_actions": ["Retry with live data."],
                "confidence": "medium",
            },
        },
    )

    result = strategy_agent(make_state(STRATEGY_MODE_LLM_ASSISTED))

    assert result["strategy_execution_mode"] == STRATEGY_MODE_RULE_BASED_FALLBACK
    assert result["llm_fallback_reason"] == "schema_validation_failed"


def test_strategy_agent_llm_assisted_falls_back_on_unparseable_text(monkeypatch) -> None:
    """Completely unparseable model text should trigger a fallback."""
    monkeypatch.setattr(
        "ecomscout_ai.agents.strategy_agent._run_llm_assisted_strategy",
        lambda state: (_ for _ in ()).throw(ValueError("No JSON object found in model response")),
    )

    result = strategy_agent(make_state(STRATEGY_MODE_LLM_ASSISTED))

    assert result["strategy_execution_mode"] == STRATEGY_MODE_RULE_BASED_FALLBACK
    assert result["llm_fallback_reason"] == "llm_output_parse_failed"
