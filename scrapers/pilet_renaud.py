from __future__ import annotations

from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text


class PiletRenaudScraper(BaseScraper):

    name = "pilet_renaud"
    use_playwright = True

    def parse_list_page(self, soup, base_url: str) -> list[dict]:

        listings: list[dict] = []

        # sélecteurs plus fiables
        cards = soup.select(
            "div.property-card, div.search-result, article"
        )

        if not cards:
            cards = soup.select("a[href*='/fr/location/']")

        for card in cards:

            link = card.find("a", href=True)

            if not link:
                continue

            url = self.absolutize(base_url, link.get("href"))

            text_blob = clean_text(card.get_text(" ", strip=True))

            title = clean_text(link.get_text(" ", strip=True))

            if not title:
                title = text_blob[:120]

            # filtre moins agressif
            keywords = [
                "commercial",
                "arcade",
                "bureau",
                "activité",
                "local",
                "surface"
            ]

            if not any(k in text_blob.lower() for k in keywords):
                continue

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
