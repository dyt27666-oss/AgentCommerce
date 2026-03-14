"""Strategy agent implementation."""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy

from ecomscout_ai.state.agent_state import AgentState

STRATEGY_MODE_RULE_BASED = "rule_based"
STRATEGY_MODE_LLM_ASSISTED = "llm_assisted"
STRATEGY_MODE_RULE_BASED_FALLBACK = "rule_based_fallback"

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


def _normalize_list(value, fallback_item: str) -> list[str]:
    """Normalize a loose LLM output value into a short string list."""
    if isinstance(value, list):
        normalized = [str(item).strip() for item in value if str(item).strip()]
        return normalized or [fallback_item]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return [fallback_item]


def _normalize_confidence(value) -> str:
    """Normalize confidence into the supported enum values."""
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"high", "medium", "low"}:
            return normalized
    return "low"


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
        "You are a market strategy assistant. Based on the JSON input, produce only a JSON object "
        "with keys market_summary, pricing_recommendation, key_risks, next_actions, confidence. "
        "confidence must be one of high, medium, low. key_risks and next_actions must be short lists. "
        "Do not include markdown or explanations.\n\n"
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


def _normalize_llm_brief(raw_brief: dict) -> dict:
    """Normalize loose LLM output into the strict decision brief schema."""
    return {
        "market_summary": str(raw_brief.get("market_summary", DEFAULT_DECISION_BRIEF["market_summary"])).strip()
        or DEFAULT_DECISION_BRIEF["market_summary"],
        "pricing_recommendation": str(
            raw_brief.get(
                "pricing_recommendation",
                DEFAULT_DECISION_BRIEF["pricing_recommendation"],
            )
        ).strip()
        or DEFAULT_DECISION_BRIEF["pricing_recommendation"],
        "key_risks": _normalize_list(
            raw_brief.get("key_risks"),
            DEFAULT_DECISION_BRIEF["key_risks"][0],
        ),
        "next_actions": _normalize_list(
            raw_brief.get("next_actions"),
            DEFAULT_DECISION_BRIEF["next_actions"][0],
        ),
        "confidence": _normalize_confidence(raw_brief.get("confidence")),
    }


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
    brief = _normalize_llm_brief(parsed)
    strategy = brief["pricing_recommendation"]
    return {"strategy": strategy, "decision_brief": brief}


def strategy_agent(state: AgentState) -> dict:
    """Generate strategy output in either rule-based or LLM-assisted mode."""
    strategy_mode = state["strategy_mode"]

    if strategy_mode == STRATEGY_MODE_LLM_ASSISTED:
        try:
            llm_result = _run_llm_assisted_strategy(state)
            return {
                "strategy": llm_result["strategy"],
                "decision_brief": _normalize_llm_brief(llm_result["decision_brief"]),
                "strategy_execution_mode": STRATEGY_MODE_LLM_ASSISTED,
            }
        except Exception:
            strategy, brief = _build_rule_based_strategy(state)
            return {
                "strategy": strategy,
                "decision_brief": brief,
                "strategy_execution_mode": STRATEGY_MODE_RULE_BASED_FALLBACK,
            }

    strategy, brief = _build_rule_based_strategy(state)
    return {
        "strategy": strategy,
        "decision_brief": brief,
        "strategy_execution_mode": STRATEGY_MODE_RULE_BASED,
    }
