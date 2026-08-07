from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re, time

class PiletRenaudScraper(BaseScraper):
    name = "pilet_renaud"
    use_playwright = False
    BASE_URL = "https://www.pilet-renaud.ch"

    # URLs à exclure — pages de navigation
    _EXCLUDED = ["/estimer", "/contact", "/vendre", "/acheter", "/accueil/search$"]

    def scrape(self) -> list[dict]:
        urls = self.urls or ["https://www.pilet-renaud.ch/fr/accueil/search/transaction/rent"]

        listings: list[dict] = []
        seen_urls: set[str] = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=self.user_agent,
                locale="fr-CH",
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()
            page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf}",
                       lambda r: r.abort())

            # Chaque URL correspond à un type de bien différent (le filtre
            # "type" du site est encodé dans le hash-fragment, ex: ARCADE,
            # DEPOT). Le site ne permet pas de combiner plusieurs types dans
            # une seule recherche, donc on parcourt les URLs une par une.
            for url in urls:
                self.logger.info(f"[pilet_renaud] Playwright → {url}")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)
                time.sleep(5)
                html = page.content()

                soup = BeautifulSoup(html, "html.parser")
                results = self.parse_list_page(soup, url)
                new_results = [r for r in results if r.get("url") not in seen_urls]
                seen_urls.update(r.get("url") for r in new_results)
                listings.extend(new_results)
                self.logger.info(f"[pilet_renaud] {url}: {len(new_results)} annonces")

            browser.close()

        self.logger.info(f"[pilet_renaud] {len(listings)} annonces trouvées au total")
        return listings

    def parse_list_page(self, soup, base_url) -> list[dict]:
        listings = []

        # Structure réelle : a.item-link > div.item#item-XXXX
        # Donc on sélectionne les liens a.item-link directement
        links = soup.select("a.item-link[href]")
        self.logger.info(f"[pilet_renaud] {len(links)} liens a.item-link trouvés")

        if not links:
            # Fallback : div.item avec id numérique
            links = []
            for div in soup.select("div.item[id]"):
                if re.match(r"item-\d+", div.get("id", "")):
                    parent = div.parent
                    if parent and parent.name == "a":
                        links.append(parent)

        for link in links:
            href = link.get("href", "")
            if not href or self._is_excluded(href):
                continue

            # Vraie annonce = URL avec ID numérique en fin
            if not re.search(r"-\d{4,}$", href):
                continue

            url = self.absolutize(self.BASE_URL, href)

            # Le div.item est à l'intérieur du lien
            card = link.select_one("div.item") or link

            title_el = (
                card.select_one("p.title") or
                card.select_one(".dotdotdot-item-title p") or
                card.select_one("h2") or
                card.select_one("h3")
            )
            title = clean_text(title_el.get_text(" ", strip=True)) if title_el else ""

            text_blob = clean_text(card.get_text(" ", strip=True))
            price_chf  = self._parse_price(text_blob)
            surface_m2 = self._parse_surface(text_blob)

            listings.append(self.make_listing(
                url=url,
                title=title,
                price_chf=price_chf,
                surface_m2=surface_m2,
                text_blob=text_blob,
                site=self.name,
                location_hint=text_blob,
            ))

        return listings

    def _is_excluded(self, href: str) -> bool:
        return any(e in href for e in self._EXCLUDED)

    def _parse_price(self, text: str) -> int | None:
        # Le loyer mensuel réel est annoncé "Loyer CHF X.-" ; il faut le
        # préférer au prix CHF/m²/an affiché en tête d'annonce (ex: "CHF
        # 450.-/m2/an"), sans quoi on stockait ce prix au m² comme s'il
        # s'agissait du loyer mensuel (ex: 450 au lieu de 3'187 CHF/mois).
        m = re.search(r"loyer\s*chf\s*([\d'’]+)", text, re.I)
        if m:
            val = int(re.sub(r"[^\d]", "", m.group(1)))
            if 300 <= val <= 200000:
                return val

        # Pas de "Loyer CHF X" (ex: "Prix sur demande") : à défaut, un
        # montant CHF isolé, à condition qu'il ne s'agisse pas d'un prix
        # au m²/an (sinon on confondrait un prix au m² avec le loyer mensuel).
        m = re.search(r"CHF\s*([\d'’]+)[.\-–]", text)
        if m:
            context_after = text[m.end():m.end() + 15].lower()
            if not re.search(r"m[²2]", context_after):
                val = int(re.sub(r"[^\d]", "", m.group(1)))
                if 300 <= val <= 200000:
                    return val
        return None

    def _parse_surface(self, text: str) -> float | None:
        m = re.search(r"(\d{2,5}[\.,]?\d*)\s*m[²2]", text, re.I)
        if m:
            return float(m.group(1).replace(",", "."))
        return None
