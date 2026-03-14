"""Main entrypoint for EcomScout-AI."""

from ecomscout_ai.graph.agent_graph import build_agent_graph
from ecomscout_ai.agents.strategy_agent import DEFAULT_DECISION_BRIEF, STRATEGY_MODE_RULE_BASED
from ecomscout_ai.state.agent_state import AgentState


def build_initial_state(user_query: str) -> AgentState:
    """Create the initial shared state for the workflow."""
    return {
        "user_query": user_query,
        "crawl_keyword": "",
        "crawl_fields": [],
        "crawl_depth": 1,
        "crawl_limit": 20,
        "crawl_status": "failed",
        "crawl_warnings": [],
        "crawl_error_type": None,
        "fallback_used": False,
        "products": [],
        "clean_data": [],
        "analysis_result": {},
        "strategy_mode": STRATEGY_MODE_RULE_BASED,
        "strategy_execution_mode": STRATEGY_MODE_RULE_BASED,
        "decision_brief": DEFAULT_DECISION_BRIEF.copy(),
        "strategy": "",
        "report": "",
    }


def main() -> None:
    """Run the graph with a fixed demo query and print the final report."""
    graph = build_agent_graph()
    initial_state = build_initial_state("Analyze bluetooth earphone market")
    result = graph.invoke(initial_state)
    print(result["report"])


if __name__ == "__main__":
    main()
