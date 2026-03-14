"""Research agent implementation."""

from ecomscout_ai.state.agent_state import AgentState


FIELD_SCHEMA = ["name", "price", "rating", "reviews", "url", "brand", "bsr", "category"]
SEARCH_FIELDS = FIELD_SCHEMA[:5]
DETAIL_FIELDS = FIELD_SCHEMA[5:]
STOP_WORDS = {"analyze", "analysis", "market", "research"}
DEPTH_TWO_HINTS = {"detail", "details", "brand", "bsr", "category"}


def research_agent(state: AgentState) -> dict:
    """Derive crawl parameters from the user query using deterministic rules."""
    query = state["user_query"].lower()
    tokens = [token.strip(" ,.!?") for token in query.split()]
    keyword_tokens = [token for token in tokens if token and token not in STOP_WORDS]
    crawl_keyword = " ".join(keyword_tokens).strip() or query.strip()

    crawl_depth = 2 if any(hint in tokens for hint in DEPTH_TWO_HINTS) else 1
    crawl_fields = SEARCH_FIELDS.copy()
    if crawl_depth == 2:
        crawl_fields.extend(DETAIL_FIELDS)

    return {
        "crawl_keyword": crawl_keyword,
        "crawl_fields": crawl_fields,
        "crawl_depth": crawl_depth,
        "crawl_limit": 20,
    }
