from __future__ import annotations

from playwright.sync_api import sync_playwright


def fetch_dynamic_html(url: str, timeout_ms: int = 90000) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, timeout=timeout_ms, wait_until="networkidle")
        html = page.content()
        browser.close()
        return html
