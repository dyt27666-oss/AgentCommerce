"""Data processing agent implementation."""

from ecomscout_ai.state.agent_state import AgentState


REQUIRED_PRODUCT_FIELDS = {"name", "price", "rating", "reviews", "url"}


def _to_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    filtered = "".join(ch for ch in text if ch.isdigit() or ch == ".")
    if not filtered:
        return None
    try:
        return float(filtered)
    except ValueError:
        return None


def _to_int(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = "".join(ch for ch in str(value) if ch.isdigit())
    return int(text) if text else None


def data_processing_agent(state: AgentState) -> dict:
    """Clean and normalize the product list returned by the crawler."""
    clean_data = []
    for product in state["products"]:
        if not isinstance(product, dict):
            continue
        if not REQUIRED_PRODUCT_FIELDS.issubset(product.keys()):
            continue

        price = _to_float(product.get("price"))
        if price is None:
            continue

        normalized = {
            "name": str(product.get("name", "")).strip(),
            "price": price,
            "rating": _to_float(product.get("rating")),
            "reviews": _to_int(product.get("reviews")),
            "url": str(product.get("url", "")).strip(),
            "brand": product.get("brand"),
            "bsr": product.get("bsr"),
            "category": product.get("category"),
        }
        if not normalized["name"] or not normalized["url"]:
            continue
        clean_data.append(normalized)
    return {"clean_data": clean_data}
