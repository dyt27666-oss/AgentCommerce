"""Report agent implementation."""

from ecomscout_ai.state.agent_state import AgentState


def report_agent(state: AgentState) -> dict:
    """Generate a Markdown report based on the workflow state."""
    product_lines = []
    for product in state["clean_data"]:
        product_lines.append(
            "- {name}: 价格 {price} RMB, 评分 {rating}, 评论数 {reviews}".format(
                name=product["name"],
                price=product["price"],
                rating=product["rating"],
                reviews=product["reviews"],
            )
        )

    if not product_lines:
        product_lines.append("- 暂无有效商品数据")

    analysis_result = state["analysis_result"]
    report = "\n".join(
        [
            "# EcomScout-AI 市场分析报告",
            "",
            "## 用户需求",
            state["user_query"],
            "",
            "## 执行计划",
            *[f"- {step}" for step in state["task_plan"]],
            "",
            "## 商品样本",
            *product_lines,
            "",
            "## 市场分析",
            f"- 样本数量: {analysis_result.get('product_count', 0)}",
            f"- 平均价格: {analysis_result.get('average_price', 0)} RMB",
            f"- 最高价格: {analysis_result.get('max_price', 0)} RMB",
            f"- 最低价格: {analysis_result.get('min_price', 0)} RMB",
            "",
            "## 策略建议",
            state["strategy"],
        ]
    )
    return {"report": report}
