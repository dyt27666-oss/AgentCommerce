"""Analysis agent implementation."""

from ecomscout_ai.state.agent_state import AgentState


def analysis_agent(state: AgentState) -> dict:
    """Calculate dataset size, price metrics, and rating distribution."""
    prices = []
    rating_distribution: dict[str, int] = {}

    for item in state["clean_data"]:
        if not isinstance(item, dict):
            continue
        price = item.get("price")
        if isinstance(price, (int, float)):
            prices.append(float(price))

        rating = item.get("rating")
        if isinstance(rating, (int, float)):
            key = f"{float(rating):.1f}"
            rating_distribution[key] = rating_distribution.get(key, 0) + 1

    if not prices:
        return {
            "analysis_result": {
                "product_count": 0,
                "avg_price": 0.0,
                "price_range": {"min": 0.0, "max": 0.0},
                "rating_distribution": {},
            }
        }

    return {
        "analysis_result": {
            "product_count": len(prices),
            "avg_price": round(sum(prices) / len(prices), 2),
            "price_range": {"min": min(prices), "max": max(prices)},
            "rating_distribution": dict(sorted(rating_distribution.items())),
        }
    }
