"""Compatibility wrapper for crawler HTTP access.

This module keeps the crawler transport behind a dedicated client so the
implementation can later move to Playwright without changing provider logic.
"""

from __future__ import annotations

import requests


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


class PageClient:
    """Minimal HTTP client for page fetching."""

    def __init__(self, timeout: int = 20) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    def fetch_text(self, url: str) -> str:
        """Fetch the page text or raise a requests exception."""
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.text
