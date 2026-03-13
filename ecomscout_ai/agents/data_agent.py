"""Data processing agent implementation."""

from ecomscout_ai.state.agent_state import AgentState


REQUIRED_PRODUCT_FIELDS = {"name", "price", "rating", "reviews"}


def data_processing_agent(state: AgentState) -> dict:
    """Clean the product list by keeping only complete product records."""
    clean_data = []
    for product in state["products"]:
        if not isinstance(product, dict):
            continue
        if not REQUIRED_PRODUCT_FIELDS.issubset(product.keys()):
            continue
        clean_data.append(product)
    return {"clean_data": clean_data}
