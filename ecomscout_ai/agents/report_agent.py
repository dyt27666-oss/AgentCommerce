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
    data_origin = "amazon_live" if state["crawl_status"] in {"success", "partial_success"} else "mock_dataset"
    price_analysis = analysis_result.get("price_analysis", {})
    review_analysis = analysis_result.get("review_analysis", {})
    brand_analysis = analysis_result.get("brand_analysis", {})
    dataset_quality = analysis_result.get("dataset_quality", {})

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
            "## Data Source",
            f"- crawler_status: {state['crawl_status']}",
            f"- data_origin: {data_origin}",
            f"- records_collected: {len(state['products'])}",
            "",
            "## Dataset Summary",
            f"- product_count: {analysis_result.get('product_count', 0)}",
            f"- cleaned_records: {len(state['clean_data'])}",
            "",
            "## Dataset Quality",
            f"- sample_size: {dataset_quality.get('sample_size', 0)}",
            f"- missing_price_ratio: {dataset_quality.get('missing_price_ratio', 0.0)}",
            f"- missing_rating_ratio: {dataset_quality.get('missing_rating_ratio', 0.0)}",
            f"- missing_brand_ratio: {dataset_quality.get('missing_brand_ratio', 0.0)}",
            "",
            "## Sample Products",
            *product_lines,
            "",
            "## Price Analysis",
            f"- avg_price: ${price_analysis.get('avg_price', 0.0):.2f}",
            f"- median_price: ${price_analysis.get('median_price', 0.0):.2f}",
            "",
            "## Price Distribution",
            f"- price_percentiles: {price_analysis.get('price_percentiles', {'p25': 0.0, 'p50': 0.0, 'p75': 0.0})}",
            f"- price_bands: {price_analysis.get('price_bands', {'low': 0, 'mid': 0, 'high': 0})}",
            f"- rating_distribution: {analysis_result.get('rating_distribution', {})}",
            "",
            "## Review Statistics",
            f"- review_avg: {review_analysis.get('review_avg', 0.0)}",
            f"- review_median: {review_analysis.get('review_median', 0.0)}",
            f"- review_distribution: {review_analysis.get('review_distribution', {'0-999': 0, '1000-2999': 0, '3000+': 0})}",
            "",
            "## Brand Overview",
            f"- brand_coverage: {brand_analysis.get('brand_coverage', 'low')}",
            f"- brand_counts: {brand_analysis.get('brand_counts', {})}",
            f"- brand_share: {brand_analysis.get('brand_share', {})}",
            "",
            "## Strategy Suggestion",
            state["strategy"],
        ]
    )
    return {"report": report}
