from __future__ import annotations

import re

from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text


class AcheterLouerScraper(BaseScraper):
    name = "acheter_louer"
    use_playwright = True
    # ~90 annonces par page, ~700 au total pour tout le canton de Genève.
    # On se limite à quelques pages par run (le reste est de toute façon
    # filtré ensuite par quartier/loyer/surface/vestiaires).
    max_pages = 4

    def parse_list_page(self, soup, base_url: str) -> list[dict]:
        # Chaque annonce est rendue par plusieurs <a href="..."> pointant vers
        # la même fiche (vignette image, lien "contact", lien texte...). Seul
        # l'un d'eux porte le texte (prix/surface/titre) ; on garde donc, pour
        # chaque URL, la version avec le plus de texte plutôt que la première
        # rencontrée (souvent vide, ex: le lien-image).
        best_blob_by_href: dict[str, str] = {}
        for link in soup.select("a[href*='/fr/location-immobilier/']"):
            href = link.get("href", "").split("#")[0]
            if not href:
                continue
            blob = clean_text(link.get_text(" ", strip=True))
            if len(blob) > len(best_blob_by_href.get(href, "")):
                best_blob_by_href[href] = blob

        listings: list[dict] = []
        for href, blob in best_blob_by_href.items():
            if not blob:
                continue
            url = self.absolutize(base_url, href)
            listings.append(self.make_listing(
                url=url,
                title=blob[:150],
                price_chf=self._parse_price(blob),
                text_blob=blob,
                site=self.name,
                location_hint=blob,
            ))

        return listings

    def _parse_price(self, text: str) -> int | None:
        # acheter-louer.ch affiche le loyer mensuel en tête de carte comme un
        # simple nombre suivi de ".–" ou ".-", sans le libellé "CHF" (ex:
        # "9'080.– 177 m2 Commercial à louer ..."). "Prix sur demande"
        # signifie qu'aucun montant n'est publié.
        m = re.match(r"\s*(\d[\d'’]*)\s*\.\s*[–\-]", text)
        if m:
            val = int(re.sub(r"[^\d]", "", m.group(1)))
            if 300 <= val <= 200000:
                return val
        return None

    def build_page_url(self, start_url: str, page_num: int) -> str | None:
        base = re.sub(r"[?&]page=\d+", "", start_url)
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}page={page_num}"
