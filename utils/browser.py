from playwright.sync_api import sync_playwright


def fetch_dynamic_html(url, timeout_ms=60000, wait_strategy="domcontentloaded"):

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        )

        page = context.new_page()

        page.goto(url, timeout=timeout_ms, wait_until=wait_strategy)

        # laisser charger le JS
        page.wait_for_timeout(3000)

        html = page.content()

        browser.close()

        return html
