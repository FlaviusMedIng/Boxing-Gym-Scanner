from __future__ import annotations

from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text


class RealAdvisorScraper(BaseScraper):
    name = "realadvisor"
    use_playwright = True

    def parse_list_page(self, soup, base_url: str) -> list[dict]:
        listings: list[dict] = []
        cards = soup.select("a[href*='/fr/louer/']") or soup.select("article a[href]")
        for link in cards:
            href = link.get("href")
            if not href:
                continue
            url = self.absolutize(base_url, href)
            blob = clean_text(link.parent.get_text(" ", strip=True) if link.parent else link.get_text(" ", strip=True))
            title = clean_text(link.get_text(" ", strip=True)) or blob[:120]
            if "/commercial" not in url and "commercial" not in blob.lower():
                continue
            listings.append(self.make_listing(url=url, title=title, text_blob=blob, site=self.name, location_hint=blob))
        return listings
