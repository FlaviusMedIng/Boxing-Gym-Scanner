import requests
from bs4 import BeautifulSoup
from utils.browser import fetch_dynamic_html


class BaseScraper:

    name = "base"
    use_playwright = False
    load_strategy = "domcontentloaded"
    timeout = 45
    user_agent = "Mozilla/5.0"

    def __init__(self, site_cfg=None, config=None, logger=None):

        self.site_cfg = site_cfg or {}
        self.config = config
        self.logger = logger

        config_urls = self.site_cfg.get("urls", [])
        class_urls = getattr(self, "urls", [])

        self.urls = config_urls or class_urls

        if not self.urls and self.logger:
            self.logger.warning(f"{self.name} has no URLs configured")

    def fetch_html(self, url):

        if self.use_playwright:
            return fetch_dynamic_html(
                url,
                timeout_ms=self.timeout * 1000,
                wait_strategy=self.load_strategy
            )

        response = requests.get(
            url,
            timeout=self.timeout,
            headers={"User-Agent": self.user_agent}
        )

        response.raise_for_status()
        return response.text

    def scrape(self):

        listings = []

        if self.logger:
            self.logger.info(f"{self.name} scraping {len(self.urls)} urls")

        for url in self.urls:

            html = self.fetch_html(url)

            soup = BeautifulSoup(html, "html.parser")

            listings.extend(self.parse_list_page(soup, url))

        return listings
