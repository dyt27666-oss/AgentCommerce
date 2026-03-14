"""Shared state definition for the EcomScout-AI workflow."""

from typing import TypedDict


class AgentState(TypedDict):
    """Shared state passed between all LangGraph nodes."""

    user_query: str
    crawl_keyword: str
    crawl_fields: list
    crawl_depth: int
    crawl_limit: int
    products: list
    clean_data: list
    analysis_result: dict
    strategy: str
    report: str
