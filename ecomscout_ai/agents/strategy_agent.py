"""Strategy agent implementation."""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from typing import Any

from ecomscout_ai.state.agent_state import AgentState

STRATEGY_MODE_RULE_BASED = "rule_based"
STRATEGY_MODE_LLM_ASSISTED = "llm_assisted"
STRATEGY_MODE_RULE_BASED_FALLBACK = "rule_based_fallback"
LLM_PARSE_STATUS_NOT_ATTEMPTED = "not_attempted"
LLM_PARSE_STATUS_PARSED = "parsed"
LLM_PARSE_STATUS_FALLBACK = "fallback"
ALLOWED_CONFIDENCE_VALUES = {"high", "medium", "low"}
MAX_LIST_ITEMS = 3
MAX_TEXT_LENGTH = 240

DEFAULT_DECISION_BRIEF = {
    "market_summary": "Insufficient data to summarize the market.",
    "pricing_recommendation": "Collect more reliable market data before finalizing pricing.",
    "key_risks": ["The current dataset is too limited for a high-confidence decision."],
    "next_actions": ["Increase data coverage before revisiting the recommendation."],
    "confidence": "low",
}


def _clone_default_brief() -> dict:
    """Return a writable copy of the default decision brief."""
    return deepcopy(DEFAULT_DECISION_BRIEF)


def _collapse_whitespace(value: str) -> str:
    """Normalize repeated whitespace without changing semantics."""
    return re.sub(r"\s+", " ", value).strip()


def _clip_text(value: str, max_length: int = MAX_TEXT_LENGTH) -> str:
    """Keep brief text concise enough for deterministic reporting."""
    if len(value) <= max_length:
        return value
    return value[: max_length - 3].rstrip() + "..."


def _normalize_text(value: Any) -> str:
    """Normalize a potentially loose text field into a compact string."""
    if value is None:
        return ""
    return _clip_text(_collapse_whitespace(str(value)))


def _normalize_confidence(value: Any) -> str:
    """Normalize confidence into the supported enum values."""
    if isinstance(value, str):
        normalized = _collapse_whitespace(value).lower()
        if normalized in ALLOWED_CONFIDENCE_VALUES:
            return normalized
    raise ValueError("confidence must be one of high, medium, low")


def _normalize_string_list(value: Any, field_name: str) -> list[str]:
    """Normalize list fields while preserving a strict output contract."""
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list of strings")

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} must be a list of strings")
        cleaned = _normalize_text(item)
        if cleaned:
            normalized.append(cleaned)
        if len(normalized) >= MAX_LIST_ITEMS:
            break

    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")

    return normalized


def _validate_and_normalize_brief(raw_brief: dict) -> dict:
    """Validate the LLM brief and return a strict normalized structure."""
    if not isinstance(raw_brief, dict):
        raise ValueError("decision_brief must be a JSON object")

    required_keys = {
        "market_summary",
        "pricing_recommendation",
        "key_risks",
        "next_actions",
        "confidence",
    }
    missing_keys = [key for key in required_keys if key not in raw_brief]
    if missing_keys:
        raise ValueError(f"decision_brief missing required keys: {', '.join(sorted(missing_keys))}")

    market_summary = _normalize_text(raw_brief["market_summary"])
    pricing_recommendation = _normalize_text(raw_brief["pricing_recommendation"])
    if not market_summary:
        raise ValueError("market_summary must be a non-empty string")
    if not pricing_recommendation:
        raise ValueError("pricing_recommendation must be a non-empty string")

    return {
        "market_summary": market_summary,
        "pricing_recommendation": pricing_recommendation,
        "key_risks": _normalize_string_list(raw_brief["key_risks"], "key_risks"),
        "next_actions": _normalize_string_list(raw_brief["next_actions"], "next_actions"),
        "confidence": _normalize_confidence(raw_brief["confidence"]),
    }


def _build_data_origin(state: AgentState) -> str:
    """Map crawl status to a data origin label for prompts and reports."""
    return "amazon_live" if state["crawl_status"] in {"success", "partial_success"} else "mock_dataset"


def _build_rule_based_strategy(state: AgentState) -> tuple[str, dict]:
    """Construct deterministic strategy text and decision brief."""
    analysis_result = state["analysis_result"]
    product_count = analysis_result.get("product_count", 0)
    price_analysis = analysis_result.get("price_analysis", {})
    percentiles = price_analysis.get(
        "price_percentiles", {"p25": 0.0, "p50": 0.0, "p75": 0.0}
    )
    avg_price = price_analysis.get("avg_price", 0.0)
    quality = analysis_result.get("dataset_quality", {})
    brand_coverage = analysis_result.get("brand_analysis", {}).get("brand_coverage", "low")

    if product_count == 0:
        strategy = (
            "The current dataset is too small to support a pricing recommendation. "
            "Collect more search results before making a market entry decision."
        )
        brief = _clone_default_brief()
        return strategy, brief

    quality_note = ""
    confidence = "high"
    key_risks = []

    if state["fallback_used"]:
        key_risks.append("The current recommendation relies on fallback data rather than a confirmed live crawl.")
        confidence = "low"
    if quality.get("missing_brand_ratio", 0.0) > 0.5 or brand_coverage == "low":
        quality_note = " Brand coverage is limited, so positioning insights should be treated cautiously."
        key_risks.append("Brand coverage is low, which weakens positioning confidence.")
        confidence = "medium" if confidence == "high" else confidence
    if quality.get("sample_size", 0) < 5:
        key_risks.append("The sample size is small and may not represent the full market.")
        confidence = "medium" if confidence == "high" else confidence

    strategy = (
        f"The core market price band sits around ${percentiles.get('p25', 0.0):.2f}-"
        f"${percentiles.get('p75', 0.0):.2f}. "
        f"A launch price near ${avg_price:.2f} is a practical starting point."
        f"{quality_note}"
    )
    brief = {
        "market_summary": (
            f"The observed market centers around a median price of "
            f"${price_analysis.get('median_price', 0.0):.2f} with {product_count} analyzed products."
        ),
        "pricing_recommendation": (
            f"Use ${avg_price:.2f} as the initial benchmark and validate against the "
            f"${percentiles.get('p25', 0.0):.2f}-${percentiles.get('p75', 0.0):.2f} core price band."
        ),
        "key_risks": key_risks or ["No major structural risks were detected in the current dataset."],
        "next_actions": [
            "Validate the pricing recommendation with another live crawl run.",
            "Compare the current product set against a second keyword or category segment.",
        ],
        "confidence": confidence,
    }
    return strategy, brief


def _build_llm_prompt(state: AgentState) -> str:
    """Build the minimal structured prompt for the LLM-assisted strategy mode."""
    payload = {
        "query": state["user_query"],
        "crawl_status": state["crawl_status"],
        "fallback_used": state["fallback_used"],
        "error_type": state["crawl_error_type"],
        "data_origin": _build_data_origin(state),
        "analysis_result": state["analysis_result"],
    }
    return (
        "You are a market strategy assistant. Based on the JSON input, output only one JSON object. "
        "Do not output markdown, code fences, prose, or explanations. "
        "Required keys: market_summary, pricing_recommendation, key_risks, next_actions, confidence. "
        "market_summary and pricing_recommendation must be short non-empty strings. "
        "key_risks and next_actions must be JSON arrays of short strings with at most 3 items each. "
        "confidence must be exactly one of: high, medium, low. "
        "If fallback_used is true, error_type is not null, or dataset quality is weak, reflect that risk in key_risks.\n\n"
        f"INPUT:\n{json.dumps(payload, ensure_ascii=True)}"
    )


def _extract_json_object(text: str) -> dict:
    """Extract a JSON object from a loose model response."""
    text = text.strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model response")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Model response JSON was not an object")
    return parsed


def _run_llm_assisted_strategy(state: AgentState) -> dict:
    """Run the LLM-assisted strategy generation."""
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")

    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    prompt = _build_llm_prompt(state)
    model = ChatOpenAI(model=model_name, temperature=0)
    response = model.invoke(prompt)
    content = getattr(response, "content", "")
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )

    parsed = _extract_json_object(str(content))
    brief = _validate_and_normalize_brief(parsed)
    strategy = brief["pricing_recommendation"]
    return {"strategy": strategy, "decision_brief": brief}


def _fallback_result(state: AgentState, reason: str) -> dict:
    """Return an honest deterministic fallback payload."""
    strategy, brief = _build_rule_based_strategy(state)
    return {
        "strategy": strategy,
        "decision_brief": brief,
        "strategy_execution_mode": STRATEGY_MODE_RULE_BASED_FALLBACK,
        "llm_parse_status": LLM_PARSE_STATUS_FALLBACK,
        "llm_fallback_reason": reason,
    }


def strategy_agent(state: AgentState) -> dict:
    """Generate strategy output in either rule-based or LLM-assisted mode."""
    strategy_mode = state["strategy_mode"]

    if strategy_mode == STRATEGY_MODE_LLM_ASSISTED:
        try:
            llm_result = _run_llm_assisted_strategy(state)
            brief = _validate_and_normalize_brief(llm_result["decision_brief"])
            return {
                "strategy": llm_result["strategy"],
                "decision_brief": brief,
                "strategy_execution_mode": STRATEGY_MODE_LLM_ASSISTED,
                "llm_parse_status": LLM_PARSE_STATUS_PARSED,
                "llm_fallback_reason": None,
            }
        except ValueError as exc:
            if "JSON object" in str(exc):
                return _fallback_result(state, "llm_output_parse_failed")
            return _fallback_result(state, "schema_validation_failed")
        except json.JSONDecodeError:
            return _fallback_result(state, "llm_output_parse_failed")
        except RuntimeError:
            return _fallback_result(state, "llm_runtime_error")
        except Exception as exc:
            if "JSON object" in str(exc):
                return _fallback_result(state, "llm_output_parse_failed")
            return _fallback_result(state, "llm_runtime_error")

    strategy, brief = _build_rule_based_strategy(state)
    return {
        "strategy": strategy,
        "decision_brief": brief,
        "strategy_execution_mode": STRATEGY_MODE_RULE_BASED,
        "llm_parse_status": LLM_PARSE_STATUS_NOT_ATTEMPTED,
        "llm_fallback_reason": None,
    }
