"""Unit tests for the Amazon crawler provider parsing helpers."""

from ecomscout_ai.crawlers.providers.amazon_provider import (
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
