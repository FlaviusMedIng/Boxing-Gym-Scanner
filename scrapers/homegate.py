from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text
import re

class HomegateScraper(BaseScraper):
    name = "homegate"
    use_playwright = True
    load_strategy = "networkidle"  # important : attendre que le JS soit chargé

    def parse_list_page(self, soup, base_url):
        listings = []

        # Sélecteur stable basé sur data-test, pas les classes CSS
        cards = soup.select('div[data-test="result-list-item"]')

        for card in cards:
            # --- URL ---
            link = card.select_one('a[href]')
            if not link:
                continue
            href = link.get("href", "")
            url = self.absolutize(base_url, href)

            # --- Adresse / titre ---
            addr_elem = card.select_one('[data-test="address"]')
            title = clean_text(addr_elem.get_text(" ", strip=True)) if addr_elem else ""

            # --- Prix ---
            price_raw = ""
            price_elem = card.select_one('[data-test="price"]')
            if price_elem:
                price_raw = clean_text(price_elem.get_text(" ", strip=True))
            price_chf = self._parse_price(price_raw)

            # --- Surface ---
            surface_m2 = None
            surface_elem = card.select_one('[data-test="surface"]')
            if surface_elem:
                surface_m2 = self._parse_surface(
                    clean_text(surface_elem.get_text(" ", strip=True))
                )

            # --- Pièces ---
            rooms = None
            rooms_elem = card.select_one('[data-test="number-of-rooms"]')
            if rooms_elem:
                rooms = clean_text(rooms_elem.get_text(" ", strip=True))

            # --- text_blob complet pour les filtres généraux ---
            text_blob = clean_text(card.get_text(" ", strip=True))

            listings.append(
                self.make_listing(
                    url=url,
                    title=title,
                    text_blob=text_blob,
                    site=self.name,
                    location_hint=title,
                    price_chf=price_chf,
                    surface_m2=surface_m2,
                    rooms=rooms,
                )
            )

        return listings

    # ------------------------------------------------------------------ #
    #  Helpers de parsing                                                  #
    # ------------------------------------------------------------------ #

    def _parse_price(self, text: str) -> int | None:
        """Extrait un entier CHF depuis '1 850.–' ou 'CHF 2'400.-'"""
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else None

    def _parse_surface(self, text: str) -> float | None:
        """Extrait un float depuis '75 m²' ou '75.5m2'"""
        m = re.search(r"(\d+[\.,]?\d*)", text)
        if m:
            return float(m.group(1).replace(",", "."))
        return None
