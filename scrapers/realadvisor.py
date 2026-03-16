from __future__ import annotations

from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text


class RealAdvisorScraper(BaseScraper):

    name = "realadvisor"

    use_playwright = True
    load_strategy = "networkidle"

    def parse_list_page(self, soup, base_url):

        listings = []

        links = soup.select("a[href*='/fr/']")

        for link in links:

            href = link.get("href")

            if not href:
                continue

            if "louer" not in href:
                continue

            url = self.absolutize(base_url, href)

            text_blob = clean_text(link.get_text(" ", strip=True))

            if not text_blob:
                continue

            listings.append(
                self.make_listing(
                    url=url,
                    title=text_blob[:120],
                    text_blob=text_blob,
                    site=self.name,
                    location_hint=text_blob
                )
            )

        return listings
