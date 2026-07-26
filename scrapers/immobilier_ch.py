from __future__ import annotations

import re

from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text


class ImmobilierChScraper(BaseScraper):
    name = "immobilier_ch"
    use_playwright = True
    # 1 page ≈ 20 annonces. immobilier.ch en compte plusieurs centaines pour
    # tout le canton ; on se limite à un nombre raisonnable de pages par run
    # (le site trie par pertinence/plus récent en premier), le reste étant de
    # toute façon filtré ensuite par quartier/loyer/surface.
    max_pages = 6

    def parse_list_page(self, soup, base_url: str) -> list[dict]:
        listings: list[dict] = []
        cards = soup.select("div.filter-item")

        for card in cards:
            link = card.select_one("a[href*='/fr/louer/bureau-commerce-industrie/geneve/']")
            if not link:
                continue

            href = link.get("href", "")
            url = self.absolutize(base_url, href)
            blob = clean_text(card.get_text(" ", strip=True))

            # La commune apparaît dans l'URL: .../geneve/{commune}/{agence}/{slug}
            commune = None
            m = re.search(r"/fr/louer/bureau-commerce-industrie/geneve/([a-z0-9\-]+)/", href)
            if m:
                commune = m.group(1).replace("-", " ")

            title = blob[:150]
            location_hint = " ".join(filter(None, [blob, commune]))

            listings.append(self.make_listing(
                url=url,
                title=title,
                text_blob=blob,
                site=self.name,
                location_hint=location_hint,
            ))

        return listings

    def build_page_url(self, start_url: str, page_num: int) -> str | None:
        # ex: https://www.immobilier.ch/fr/louer/commercial-industriel/geneve/canton
        #  -> https://www.immobilier.ch/fr/louer/commercial-industriel/geneve/canton/page-2
        base = start_url.rstrip("/")
        base = re.sub(r"/page-\d+$", "", base)
        return f"{base}/page-{page_num}"
