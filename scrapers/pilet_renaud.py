from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text


class PiletRenaudScraper(BaseScraper):

    name = "pilet_renaud"

    use_playwright = True

    load_strategy = "domcontentloaded"

    urls = [
        "https://www.pilet-renaud.ch/fr/accueil/search/transaction/rent"
    ]

    def parse_list_page(self, soup, base_url):

        listings = []

        cards = soup.select("div.property-card, div.search-result, article")

        for card in cards:

            link = card.find("a", href=True)

            if not link:
                continue

            url = self.absolutize(base_url, link["href"])

            blob = clean_text(card.get_text(" ", strip=True))

            title = clean_text(link.get_text()) or blob[:100]

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
