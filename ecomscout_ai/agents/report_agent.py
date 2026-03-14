"""Report agent implementation."""

from ecomscout_ai.state.agent_state import AgentState


def report_agent(state: AgentState) -> dict:
    """Generate a Markdown report based on the workflow state."""
    product_lines = []
    for product in state["clean_data"]:
        product_lines.append(
            "- {name} | price=${price:.2f} | rating={rating} | reviews={reviews} | url={url}".format(
                name=product["name"],
                price=product["price"],
                rating=product["rating"],
                reviews=product["reviews"],
                url=product.get("url", ""),
            )
        )

    if not product_lines:
        product_lines.append("- No valid product records were available after cleaning.")

    analysis_result = state["analysis_result"]
    report = "\n".join(
        [
            "# Market Analysis Report",
            "",
            "## Query",
            state["user_query"],
            "",
            "## Crawl Configuration",
            f"- keyword: {state['crawl_keyword']}",
            f"- fields: {', '.join(state['crawl_fields'])}",
            f"- depth: {state['crawl_depth']}",
            f"- limit: {state['crawl_limit']}",
            "",
            "## Dataset Summary",
            f"- product_count: {analysis_result.get('product_count', 0)}",
            f"- cleaned_records: {len(state['clean_data'])}",
            "",
            "## Sample Products",
            *product_lines,
            "",
            "## Price Analysis",
            f"- avg_price: ${analysis_result.get('avg_price', 0.0):.2f}",
            (
                f"- price_range: ${analysis_result.get('price_range', {}).get('min', 0.0):.2f} "
                f"to ${analysis_result.get('price_range', {}).get('max', 0.0):.2f}"
            ),
            (
                "- rating_distribution: "
                f"{analysis_result.get('rating_distribution', {})}"
            ),
            "",
            "## Strategy Suggestion",
            state["strategy"],
        ]
    )
    return {"report": report}
