"""Amazon crawler provider."""

from __future__ import annotations

from requests import HTTPError, RequestException, Timeout
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from ecomscout_ai.crawlers.models import ProductRecord
from ecomscout_ai.crawlers.playwright_client import PageClient

AMAZON_BASE_URL = "https://www.amazon.com"
DETAIL_FETCH_LIMIT = 3
RESULT_CARD_SELECTOR = 'div[data-component-type="s-search-result"]'


def _clean_price(value: str | None) -> float | None:
    if not value:
        return None
    filtered = "".join(ch for ch in value if ch.isdigit() or ch == ".")
    if not filtered:
        return None
    try:
        return float(filtered)
    except ValueError:
        return None


def _clean_reviews(value: str | None) -> int | None:
    if not value:
        return None
    filtered = "".join(ch for ch in value if ch.isdigit())
    if not filtered:
        return None
    return int(filtered)


def _clean_rating(value: str | None) -> float | None:
    if not value:
        return None
    number = value.split(" ")[0]
    try:
        return float(number)
    except ValueError:
        return None


def _extract_text(node) -> str | None:
    if node is None:
        return None
    text = node.get_text(" ", strip=True)
    return text or None


def classify_search_page(html: str) -> str:
    """Classify the Amazon search page state before parsing results."""
    html_lower = html.lower()
    if "validatecaptcha" in html_lower or "type the characters you see" in html_lower:
        return "blocked"
    if "sorry, something went wrong" in html_lower or "dogsofamazon" in html_lower:
        return "error_page"

    soup = BeautifulSoup(html, "html.parser")
    result_cards = soup.select(RESULT_CARD_SELECTOR)
    if result_cards:
        return "results"

    empty_markers = [
        "no results for",
        "did not match any products",
        "0 results",
    ]
    if any(marker in html_lower for marker in empty_markers):
        return "empty_results"

    return "selector_mismatch"


def parse_search_results_html(html: str, limit: int) -> list[dict]:
    """Parse Amazon search results HTML into normalized product dictionaries."""
    soup = BeautifulSoup(html, "html.parser")
    products: list[dict] = []

    for result in soup.select(RESULT_CARD_SELECTOR):
        card_text = result.get_text(" ", strip=True).lower()
        if not card_text or "sponsored" in card_text:
            continue

        title_node = result.select_one("h2 a span") or result.select_one("h2 span")
        link_node = result.select_one("h2 a")
        price_node = (
            result.select_one(".a-price .a-offscreen")
            or result.select_one(".a-price-whole")
        )
        rating_node = result.select_one(".a-icon-alt")
        reviews_node = (
            result.select_one("span[aria-label*='ratings']")
            or result.select_one(".s-underline-text")
            or result.select_one("a[href*='#customerReviews'] span")
        )

        name = _extract_text(title_node)
        price = _clean_price(_extract_text(price_node))
        href = link_node.get("href") if link_node else None
        if not name or price is None or not href:
            continue

        record = ProductRecord(
            name=name,
            price=price,
            rating=_clean_rating(_extract_text(rating_node)),
            reviews=_clean_reviews(_extract_text(reviews_node)),
            url=urljoin(AMAZON_BASE_URL, href),
        )
        products.append(record.to_dict())
        if len(products) >= limit:
            break

    return products


def parse_product_detail_html(html: str) -> dict:
    """Parse optional detail fields from an Amazon product page."""
    soup = BeautifulSoup(html, "html.parser")

    brand_text = _extract_text(soup.select_one("#bylineInfo"))
    brand = None
    if brand_text:
        brand = brand_text.replace("Visit the", "").replace("Store", "").strip()

    bsr = None
    bullets = soup.select("#detailBulletsWrapper_feature_div li")
    for bullet in bullets:
        text = _extract_text(bullet)
        if text and "Best Sellers Rank" in text:
            bsr = text.replace("Best Sellers Rank", "").strip()
            break

    category = _extract_text(
        soup.select_one("#wayfinding-breadcrumbs_feature_div ul li a")
    )

    return {"brand": brand, "bsr": bsr, "category": category}


class AmazonProvider:
    """Fetch products from Amazon search results and optional detail pages."""

    def __init__(self, client: PageClient | None = None) -> None:
        self.client = client or PageClient()

    def fetch_products(
        self,
        keyword: str,
        fields: list[str],
        depth: int,
        limit: int,
    ) -> dict:
        """Fetch normalized Amazon products for the given crawl parameters."""
        search_url = f"{AMAZON_BASE_URL}/s?k={quote_plus(keyword)}"

        try:
            search_html = self.client.fetch_text(search_url)
        except Timeout:
            return self._with_fallback(keyword, depth, limit, "timeout", [])
        except RequestException:
            return self._with_fallback(keyword, depth, limit, "network_error", [])

        page_state = classify_search_page(search_html)
        if page_state == "blocked":
            return self._with_fallback(keyword, depth, limit, "blocked_page", [])
        if page_state == "empty_results":
            return self._failed("empty_results")
        if page_state in {"error_page", "selector_mismatch"}:
            return self._with_fallback(keyword, depth, limit, page_state, [])

        products = parse_search_results_html(search_html, limit=limit)
        if not products:
            return self._with_fallback(keyword, depth, limit, "selector_mismatch", [])

        warnings: list[str] = []
        crawl_status = "success"

        if depth >= 2 and any(field in fields for field in ("brand", "bsr", "category")):
            detail_failures = self._enrich_product_details(products)
            if detail_failures:
                warnings.append("detail_fetch_failed")
                crawl_status = "partial_success"

        return {
            "products": products[:limit],
            "crawl_status": crawl_status,
            "warnings": warnings,
            "error_type": None,
            "fallback_used": False,
        }

    def _enrich_product_details(self, products: list[dict]) -> int:
        failures = 0
        for product in products[:DETAIL_FETCH_LIMIT]:
            try:
                detail_html = self.client.fetch_text(product["url"])
                product.update(parse_product_detail_html(detail_html))
            except Exception:
                failures += 1
        return failures

    def _with_fallback(self, keyword: str, depth: int, limit: int, error_type: str, warnings: list[str]) -> dict:
        fallback_products = self._fallback_products(keyword, depth, limit)
        if fallback_products:
            return {
                "products": fallback_products,
                "crawl_status": "fallback",
                "warnings": warnings,
                "error_type": error_type,
                "fallback_used": True,
            }
        return self._failed(error_type)

    def _failed(self, error_type: str) -> dict:
        return {
            "products": [],
            "crawl_status": "failed",
            "warnings": [],
            "error_type": error_type,
            "fallback_used": False,
        }

    def _fallback_products(self, keyword: str, depth: int, limit: int) -> list[dict]:
        seed = keyword.title() or "Amazon Product"
        fallback = [
            ProductRecord(
                name=f"{seed} A",
                price=199.0,
                rating=4.6,
                reviews=3201,
                url=f"{AMAZON_BASE_URL}/dp/mock-product-a",
                brand="SoundMax" if depth >= 2 else None,
                bsr="#128 in Electronics" if depth >= 2 else None,
                category="Electronics" if depth >= 2 else None,
            ).to_dict(),
            ProductRecord(
                name=f"{seed} B",
                price=249.0,
                rating=4.4,
                reviews=1850,
                url=f"{AMAZON_BASE_URL}/dp/mock-product-b",
                brand="AudioNova" if depth >= 2 else None,
                bsr="#256 in Headphones" if depth >= 2 else None,
                category="Headphones" if depth >= 2 else None,
            ).to_dict(),
            ProductRecord(
                name=f"{seed} C",
                price=299.0,
                rating=4.7,
                reviews=4100,
                url=f"{AMAZON_BASE_URL}/dp/mock-product-c",
                brand="WavePeak" if depth >= 2 else None,
                bsr="#388 in Earbud Headphones" if depth >= 2 else None,
                category="Earbud Headphones" if depth >= 2 else None,
            ).to_dict(),
        ]
        return fallback[:limit]
