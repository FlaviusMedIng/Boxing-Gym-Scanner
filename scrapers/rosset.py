from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text


class RossetScraper(BaseScraper):

    name = "rosset"

    use_playwright = False

    urls = [
        "https://www.rosset.ch/location/locaux-commerciaux/all/geneve/"
    ]

    def parse_list_page(self, soup, base_url):

        listings = []

        cards = soup.select("article")

        for card in cards:

            link = card.find("a", href=True)

            if not link:
                continue

            url = self.absolutize(base_url, link["href"])

            blob = clean_text(card.get_text(" ", strip=True))

            title = clean_text(link.get_text())

            listings.append(
                self.make_listing(
                    url=url,
                    title=title,
                    text_blob=blob,
                    site=self.name,
                    location_hint=blob
                )
            )

        return listings
