"""Unit tests for the Amazon crawler provider parsing helpers."""

from requests import HTTPError

from ecomscout_ai.crawlers.providers.amazon_provider import (
    AmazonProvider,
    parse_product_detail_html,
    parse_search_results_html,
)


SEARCH_HTML = """
<html>
  <body>
    <div data-component-type="s-search-result">
      <h2><a href="/product-a"><span>Bluetooth Earphone A</span></a></h2>
      <span class="a-price"><span class="a-offscreen">$199.99</span></span>
      <i class="a-icon-star-small"><span class="a-icon-alt">4.6 out of 5 stars</span></i>
      <span class="a-size-base s-underline-text">3,201</span>
    </div>
    <div data-component-type="s-search-result">
      <h2><a href="/product-b"><span>Bluetooth Earphone B</span></a></h2>
      <span class="a-price"><span class="a-offscreen">$249.00</span></span>
      <i class="a-icon-star-small"><span class="a-icon-alt">4.4 out of 5 stars</span></i>
      <span class="a-size-base s-underline-text">1,850</span>
    </div>
    <div data-component-type="s-search-result">
      <span>Sponsored</span>
      <h2><a href="/sponsored-product"><span>Sponsored Product</span></a></h2>
      <span class="a-price"><span class="a-offscreen">$159.00</span></span>
    </div>
    <div data-component-type="s-search-result">
      <h2><a href="/missing-price"><span>Missing Price Product</span></a></h2>
    </div>
  </body>
</html>
"""


DETAIL_HTML = """
<html>
  <body>
    <a id="bylineInfo">Visit the SoundMax Store</a>
    <div id="detailBulletsWrapper_feature_div">
      <ul>
        <li><span><span>Best Sellers Rank</span><span>#128 in Electronics</span></span></li>
        <li><span><span>Item model number</span><span>SM-100</span></span></li>
      </ul>
    </div>
    <div id="wayfinding-breadcrumbs_feature_div">
      <ul>
        <li><span><a>Electronics</a></span></li>
      </ul>
    </div>
  </body>
</html>
"""


def test_parse_search_results_html_extracts_normalized_products() -> None:
    """The search page parser should extract normalized product records."""
    products = parse_search_results_html(SEARCH_HTML, limit=5)

    assert len(products) == 2
    assert products[0] == {
        "name": "Bluetooth Earphone A",
        "price": 199.99,
        "rating": 4.6,
        "reviews": 3201,
        "url": "https://www.amazon.com/product-a",
        "brand": None,
        "bsr": None,
        "category": None,
    }


def test_parse_product_detail_html_extracts_brand_bsr_and_category() -> None:
    """The detail page parser should extract the optional detail fields."""
    detail = parse_product_detail_html(DETAIL_HTML)

    assert detail == {
        "brand": "SoundMax",
        "bsr": "#128 in Electronics",
        "category": "Electronics",
    }


class FakeClient:
    """Simple client stub used to control crawler responses."""

    def __init__(self, responses: dict[str, str] | None = None, error_urls: set[str] | None = None):
        self.responses = responses or {}
        self.error_urls = error_urls or set()

    def fetch_text(self, url: str) -> str:
        if url in self.error_urls:
            raise HTTPError(f"blocked url: {url}")
        if url not in self.responses:
            raise HTTPError(f"missing url: {url}")
        return self.responses[url]


def test_amazon_provider_uses_fallback_only_after_real_attempt_fails() -> None:
    """The provider should attempt a live crawl first and fall back on failure."""
    provider = AmazonProvider(client=FakeClient(error_urls={"https://www.amazon.com/s?k=bluetooth+earphone"}))

    result = provider.fetch_products(
        keyword="bluetooth earphone",
        fields=["name", "price", "rating", "reviews", "url"],
        depth=1,
        limit=3,
    )

    assert result["crawl_status"] == "fallback"
    assert len(result["products"]) == 3
    assert result["products"][0]["url"].endswith("mock-product-a")


def test_amazon_provider_marks_partial_success_when_detail_fetch_fails() -> None:
    """The provider should keep live products and mark partial success if details fail."""
    search_url = "https://www.amazon.com/s?k=bluetooth+earphone"
    detail_url = "https://www.amazon.com/product-a"
    provider = AmazonProvider(
        client=FakeClient(
            responses={search_url: SEARCH_HTML},
            error_urls={detail_url},
        )
    )

    result = provider.fetch_products(
        keyword="bluetooth earphone",
        fields=["name", "price", "rating", "reviews", "url", "brand", "bsr", "category"],
        depth=2,
        limit=2,
    )

    assert result["crawl_status"] == "partial_success"
    assert len(result["products"]) == 2
    assert result["products"][0]["url"] == detail_url
    assert result["products"][0]["brand"] is None
