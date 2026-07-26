from __future__ import annotations

from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text


class NaefScraper(BaseScraper):
    name = "naef"
    use_playwright = True

    def parse_list_page(self, soup, base_url: str) -> list[dict]:
        listings: list[dict] = []
        cards = soup.select("a.d-block[href*='/location/']")

        for card in cards:
            href = card.get("href", "").split("?")[0]
            if not href:
                continue
            url = self.absolutize(base_url, href)
            blob = clean_text(card.get_text(" ", strip=True))
            if not blob:
                continue

            listings.append(self.make_listing(
                url=url,
                title=blob[:150],
                text_blob=blob,
                site=self.name,
                location_hint=blob,
            ))

        return listings
