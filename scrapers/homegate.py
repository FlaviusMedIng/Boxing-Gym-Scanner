from __future__ import annotations

from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text


class HomegateScraper(BaseScraper):
    name = "homegate"
    use_playwright = True

    def parse_list_page(self, soup, base_url: str) -> list[dict]:
        listings: list[dict] = []
        cards = soup.select("article") or soup.select("[data-test='result-list-item']")
        for card in cards:
            link = card.find("a", href=True)
            if not link:
                continue
            url = self.absolutize(base_url, link.get("href"))
            title = clean_text(link.get_text(" ", strip=True)) or clean_text(card.get_text(" ", strip=True))[:120]
            blob = clean_text(card.get_text(" ", strip=True))
            listings.append(self.make_listing(url=url, title=title, text_blob=blob, site=self.name, location_hint=blob))
        return listings
