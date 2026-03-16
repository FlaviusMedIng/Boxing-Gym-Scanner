from playwright.sync_api import sync_playwright


def fetch_dynamic_html(url, timeout_ms=45000):

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox"]
        )

        context = browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64)"
        )

        page = context.new_page()

        page.goto(
            url,
            timeout=timeout_ms,
            wait_until="domcontentloaded"
        )

        # laisser le JS charger les listings
        page.wait_for_timeout(3000)

        html = page.content()

        browser.close()

        return html
