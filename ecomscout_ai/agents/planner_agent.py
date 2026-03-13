"""Planner agent implementation."""

from ecomscout_ai.state.agent_state import AgentState


def planner_agent(state: AgentState) -> dict:
    """Generate a fixed task plan for the e-commerce analysis workflow."""
    _ = state["user_query"]
    return {
        "task_plan": [
            "crawl products",
            "clean data",
            "analyze market",
            "generate strategy",
            "generate report",
        ]
    }
