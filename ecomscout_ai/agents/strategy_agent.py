"""Strategy agent implementation."""

from ecomscout_ai.state.agent_state import AgentState


def strategy_agent(state: AgentState) -> dict:
    """Generate a simple pricing strategy from the analysis result."""
    analysis_result = state["analysis_result"]
    product_count = analysis_result.get("product_count", 0)
    min_price = analysis_result.get("min_price", 0)
    max_price = analysis_result.get("max_price", 0)
    average_price = analysis_result.get("average_price", 0)

    if product_count == 0:
        return {"strategy": "当前样本不足，建议先补充商品数据后再制定定价策略。"}

    return {
        "strategy": (
            f"当前市场价格区间约为 {min_price}-{max_price} RMB，"
            f"建议优先考虑 {round(average_price)} RMB 左右的切入定价。"
        )
    }
