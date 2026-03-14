"""Strategy agent implementation."""

from ecomscout_ai.state.agent_state import AgentState


def strategy_agent(state: AgentState) -> dict:
    """Generate a simple pricing strategy from the analysis result."""
    analysis_result = state["analysis_result"]
    product_count = analysis_result.get("product_count", 0)
    price_range = analysis_result.get("price_range", {"min": 0.0, "max": 0.0})
    min_price = price_range.get("min", 0.0)
    max_price = price_range.get("max", 0.0)
    average_price = analysis_result.get("avg_price", 0.0)

    if product_count == 0:
        return {
            "strategy": (
                "The current dataset is too small to support a pricing recommendation. "
                "Collect more search results before making a market entry decision."
            )
        }

    return {
        "strategy": (
            f"The current market spans roughly ${min_price:.2f}-${max_price:.2f}. "
            f"A launch price near ${average_price:.2f} is a practical starting point."
        )
    }
