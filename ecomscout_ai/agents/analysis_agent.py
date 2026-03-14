"""Analysis agent implementation."""

from ecomscout_ai.analysis.brand_analysis import analyze_brands
from ecomscout_ai.analysis.price_analysis import analyze_prices
from ecomscout_ai.analysis.quality_metrics import analyze_quality
from ecomscout_ai.analysis.review_analysis import analyze_reviews
from ecomscout_ai.state.agent_state import AgentState


def analysis_agent(state: AgentState) -> dict:
    """Calculate richer price, review, brand, and quality analytics."""
    rating_distribution: dict[str, int] = {}

    for item in state["clean_data"]:
        if not isinstance(item, dict):
            continue
        rating = item.get("rating")
        if isinstance(rating, (int, float)):
            key = f"{float(rating):.1f}"
            rating_distribution[key] = rating_distribution.get(key, 0) + 1

    return {
        "analysis_result": {
            "product_count": len(state["clean_data"]),
            "price_analysis": analyze_prices(state["clean_data"]),
            "review_analysis": analyze_reviews(state["clean_data"]),
            "brand_analysis": analyze_brands(state["clean_data"]),
            "dataset_quality": analyze_quality(state["clean_data"]),
            "rating_distribution": dict(sorted(rating_distribution.items())),
        }
    }
