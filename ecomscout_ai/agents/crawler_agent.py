"""Crawler agent implementation."""

from ecomscout_ai.state.agent_state import AgentState


def crawler_agent(state: AgentState) -> dict:
    """Return mock product data for the first version skeleton.

    TODO: Replace this mock payload with a real crawler implementation later.
    """

    _ = state["task_plan"]
    products = [
        {"name": "蓝牙耳机 A", "price": 199, "rating": 4.7, "reviews": 3200},
        {"name": "蓝牙耳机 B", "price": 249, "rating": 4.5, "reviews": 1800},
        {"name": "蓝牙耳机 C", "price": 299, "rating": 4.6, "reviews": 2400},
    ]
    return {"products": products}
