from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text


class HomegateScraper(BaseScraper):

    name = "homegate"

    use_playwright = True

    load_strategy = "domcontentloaded"

    urls = [
        "https://www.homegate.ch/rent/industrial-object/city-geneva/matching-list"
    ]

    def parse_list_page(self, soup, base_url):

        listings = []

        cards = soup.select("a[href*='/rent/']")

        for link in cards:

            url = self.absolutize(base_url, link.get("href"))

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
