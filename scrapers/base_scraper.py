import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


class BaseScraper:

    name = "base"

    def __init__(self, urls, timeout=20):

        self.urls = urls
        self.timeout = timeout
        self.user_agent = "Mozilla/5.0"

    def absolutize(self, base, href):

        return urljoin(base, href)

    def fetch_html(self, url):

        response = requests.get(
            url,
            timeout=self.timeout,
            headers={"User-Agent": self.user_agent}
        )

        response.raise_for_status()

        return response.text

    def make_listing(
        self,
        url,
        title=None,
        price=None,
        surface=None,
        description=None,
        district=None
    ):

        return {
            "url": url,
            "title": title,
            "price": price,
            "surface": surface,
            "description": description,
            "district": district,
            "site": self.name
        }

    def scrape(self):

        listings = []

        for url in self.urls:

            html = self.fetch_html(url)

            soup = BeautifulSoup(html, "html.parser")

            results = self.parse_list_page(soup, url)

            listings.extend(results)

        return listings
