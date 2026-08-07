from __future__ import annotations

import re

from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text


class NetimmoScraper(BaseScraper):
    name = "netimmo"
    use_playwright = True

    def build_page_url(self, start_url: str, page_num: int) -> str | None:
        # Pagination via ?p=N (et non ?page=N, qui est ignoré côté serveur
        # par cette appli SvelteKit et renvoie silencieusement la page 1).
        base = re.sub(r"[?&]p=\d+", "", start_url)
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}p={page_num}"

    def parse_list_page(self, soup, base_url: str) -> list[dict]:
        listings = []

        for link in soup.select("a[href*='/a-louer/']"):
            href = link.get("href", "")
            # Une vraie fiche annonce se termine par un ID numérique
            # (ex: .../5-rue-de-saint-leger-1205-geneve-i22772093).
            if not re.search(r"-i\d+$", href):
                continue

            url = self.absolutize(base_url, href)
            blob = clean_text(link.get_text(" ", strip=True))
            if not blob:
                continue

            listings.append(
                self.make_listing(
                    url=url,
                    title=blob[:150],
                    text_blob=blob,
                    site=self.name,
                    location_hint=blob,
                )
            )

        return listings
