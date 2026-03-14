"""Strategy agent implementation."""

from ecomscout_ai.state.agent_state import AgentState


def strategy_agent(state: AgentState) -> dict:
    """Generate a simple pricing strategy from the richer analysis output."""
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
        return {
            "strategy": (
                "The current dataset is too small to support a pricing recommendation. "
                "Collect more search results before making a market entry decision."
            )
        }

    quality_note = ""
    if quality.get("missing_brand_ratio", 0.0) > 0.5 or brand_coverage == "low":
        quality_note = " Brand coverage is limited, so positioning insights should be treated cautiously."

    return {
        "strategy": (
            f"The core market price band sits around ${percentiles.get('p25', 0.0):.2f}-"
            f"${percentiles.get('p75', 0.0):.2f}. "
            f"A launch price near ${avg_price:.2f} is a practical starting point."
            f"{quality_note}"
        )
    }
