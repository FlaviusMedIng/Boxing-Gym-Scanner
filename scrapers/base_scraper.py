import requests
from bs4 import BeautifulSoup

from utils.browser import fetch_dynamic_html


class BaseScraper:

    name = "base"

    use_playwright = False

    load_strategy = "domcontentloaded"

    timeout = 45

    user_agent = "Mozilla/5.0"

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

        for url in self.urls:

            html = self.fetch_html(url)

            soup = BeautifulSoup(html, "html.parser")

            listings.extend(self.parse_list_page(soup, url))

        return listings
