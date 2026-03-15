from __future__ import annotations

from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text


class PiletRenaudScraper(BaseScraper):
    name = "pilet_renaud"
    use_playwright = True

    def parse_list_page(self, soup, base_url: str) -> list[dict]:
        listings: list[dict] = []
        cards = soup.select("article") or soup.select("a[href]")
        for card in cards:
            link = card.find("a", href=True) if hasattr(card, "find") else card if getattr(card, "name", "") == "a" else None
            if not link:
                continue
            url = self.absolutize(base_url, link.get("href"))
            blob = clean_text(card.parent.get_text(" ", strip=True) if getattr(card, "name", "") == "a" and card.parent else card.get_text(" ", strip=True))
            title = clean_text(link.get_text(" ", strip=True)) or blob[:120]
            if "commercial" not in blob.lower() and "arcade" not in blob.lower() and "bureau" not in blob.lower():
                continue
            listings.append(self.make_listing(url=url, title=title, text_blob=blob, site=self.name, location_hint=blob))
        return listings
