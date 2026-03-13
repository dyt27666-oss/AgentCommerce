"""Analysis agent implementation."""

from ecomscout_ai.state.agent_state import AgentState


def analysis_agent(state: AgentState) -> dict:
    """Calculate basic price statistics from the cleaned product data."""
    prices = [
        item["price"]
        for item in state["clean_data"]
        if isinstance(item, dict) and isinstance(item.get("price"), (int, float))
    ]

    if not prices:
        return {
            "analysis_result": {
                "average_price": 0,
                "max_price": 0,
                "min_price": 0,
                "product_count": 0,
            }
        }

    return {
        "analysis_result": {
            "average_price": round(sum(prices) / len(prices), 2),
            "max_price": max(prices),
            "min_price": min(prices),
            "product_count": len(prices),
        }
    }
