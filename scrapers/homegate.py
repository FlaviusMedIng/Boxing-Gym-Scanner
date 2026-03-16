from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text


class HomegateScraper(BaseScraper):

    name = "homegate"
    use_playwright = True
    load_strategy = "domcontentloaded"

    def __init__(self, site_cfg, config, logger):
        super().__init__(site_cfg, config, logger)

        self.urls = [
            "https://www.homegate.ch/rent/industrial-object/city-geneva/matching-list"
        ]

    def parse_list_page(self, soup, base_url):

        listings = []

        cards = soup.select("a[data-testid='listing-link']")

        for link in cards:

            href = link.get("href")

            if not href:
                continue

            url = self.absolutize(base_url, href)

            text_blob = clean_text(link.parent.get_text(" ", strip=True))
            title = clean_text(link.get_text())

            listings.append(
                self.make_listing(
                    url=url,
                    title=title,
                    text_blob=text_blob,
                    site=self.name,
                    location_hint=text_blob
                )
            )

        return listings
