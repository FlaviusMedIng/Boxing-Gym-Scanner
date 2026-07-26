from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text


class RossetScraper(BaseScraper):

    name = "rosset"

    use_playwright = True

    # Le site a été refait (nouvelle plateforme) : les anciennes URLs
    # /location/locaux-commerciaux/... renvoient un 404. La liste des biens
    # à louer est maintenant unique (tous types) sur /louer et se filtre
    # côté client ; on garde ici uniquement les catégories pertinentes pour
    # une salle de sport (arcade, bureau, local industriel/commercial).
    urls = [
        "https://www.rosset.ch/louer"
    ]

    _RELEVANT_CATEGORIES = ["/arcade/", "/bureau/", "/industrial/", "/commercial/"]

    def parse_list_page(self, soup, base_url):
        listings = []

        cards = soup.select("a.property-card[href^='/louer/']")

        for card in cards:
            href = card.get("href", "")
            if not any(cat in href for cat in self._RELEVANT_CATEGORIES):
                continue

            url = self.absolutize(base_url, href)
            blob = clean_text(card.get_text(" ", strip=True))
            title = blob[:150]

            listings.append(
                self.make_listing(
                    url=url,
                    title=title,
                    text_blob=blob,
                    site=self.name,
                    location_hint=blob,
                )
            )

        return listings
