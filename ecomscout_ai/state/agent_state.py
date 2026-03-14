"""Shared state definition for the EcomScout-AI workflow."""

from typing import TypedDict


class AgentState(TypedDict):
    """Shared state passed between all LangGraph nodes."""

    user_query: str
    crawl_keyword: str
    crawl_fields: list
    crawl_depth: int
    crawl_limit: int
    crawl_status: str
    crawl_warnings: list
    crawl_error_type: str | None
    fallback_used: bool
    products: list
    clean_data: list
    analysis_result: dict
    strategy_mode: str
    strategy_execution_mode: str
    decision_brief: dict
    strategy: str
    report: str
