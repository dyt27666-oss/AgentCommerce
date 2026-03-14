"""LangGraph workflow assembly for EcomScout-AI."""

from langgraph.graph import END, START, StateGraph

from ecomscout_ai.agents.analysis_agent import analysis_agent
from ecomscout_ai.agents.crawler_agent import crawler_agent
from ecomscout_ai.agents.data_agent import data_processing_agent
from ecomscout_ai.agents.planner_agent import planner_agent
from ecomscout_ai.agents.research_agent import research_agent
from ecomscout_ai.agents.report_agent import report_agent
from ecomscout_ai.agents.strategy_agent import strategy_agent
from ecomscout_ai.state.agent_state import AgentState


def build_agent_graph():
    """Build and compile the sequential multi-agent workflow graph."""
    graph_builder = StateGraph(AgentState)

    graph_builder.add_node("planner", planner_agent)
    graph_builder.add_node("research", research_agent)
    graph_builder.add_node("crawler", crawler_agent)
    graph_builder.add_node("data_processing", data_processing_agent)
    graph_builder.add_node("analysis", analysis_agent)
    graph_builder.add_node("strategy", strategy_agent)
    graph_builder.add_node("report", report_agent)

    graph_builder.add_edge(START, "planner")
    graph_builder.add_edge("planner", "research")
    graph_builder.add_edge("research", "crawler")
    graph_builder.add_edge("crawler", "data_processing")
    graph_builder.add_edge("data_processing", "analysis")
    graph_builder.add_edge("analysis", "strategy")
    graph_builder.add_edge("strategy", "report")
    graph_builder.add_edge("report", END)

    return graph_builder.compile()
