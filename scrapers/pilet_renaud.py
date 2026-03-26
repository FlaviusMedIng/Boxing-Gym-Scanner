from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re, time

class PiletRenaudScraper(BaseScraper):
    name = "pilet_renaud"
    use_playwright = False
    BASE_URL = "https://www.pilet-renaud.ch"

    def scrape(self) -> list[dict]:
        url = self.urls[0] if self.urls else \
            "https://www.pilet-renaud.ch/fr/accueil/search/transaction/rent"

        self.logger.info(f"[pilet_renaud] Playwright → {url}")
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
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(5)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")
        results = self.parse_list_page(soup, url)
        passed = [l for l in results if self.matches_filters(l)]
        self.logger.info(
            f"[pilet_renaud] {len(results)} annonces, {len(passed)} après filtrage"
        )
        return passed

    def parse_list_page(self, soup, base_url) -> list[dict]:
        listings = []

        # Sélecteur exact issu du debug : div.item avec id="item-XXXX"
        cards = soup.select("div.item")
        self.logger.info(f"[pilet_renaud] {len(cards)} cartes div.item trouvées")

        for card in cards:
            # Le lien est a.item-link qui CONTIENT la carte
            # ou un <a> parent — on cherche dans les deux sens
            link = card.select_one("a.item-link") or card.select_one("a[href]")

            # Parfois la carte EST à l'intérieur du lien
            if not link:
                parent = card.parent
                if parent and parent.name == "a":
                    link = parent

            if not link:
                continue

            href = link.get("href", "")
            url  = self.absolutize(self.BASE_URL, href)

            # Titre : p.title dans div.dotdotdot-item-title
            title_el = (
                card.select_one("p.title") or
                card.select_one(".dotdotdot-item-title p") or
                card.select_one("h2") or
                card.select_one("h3")
            )
            title = clean_text(title_el.get_text(" ", strip=True)) if title_el else ""

            # Prix — chercher dans tout le texte de la carte
            text_blob = clean_text(card.get_text(" ", strip=True))
            price_chf = self._parse_price(text_blob)

            # Surface
            surface_m2 = self._parse_surface(text_blob)

            # Localisation depuis l'ID de la carte ex: item-8372
            item_id = card.get("id", "")

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

    def _parse_price(self, text: str) -> int | None:
        # Cherche des montants CHF type "2'400.-" ou "2 400 CHF"
        m = re.search(r"(\d[\d'\s]{2,})\s*(?:CHF|fr\.?|\.–|-)", text, re.I)
        if m:
            digits = re.sub(r"[^\d]", "", m.group(1))
            val = int(digits) if digits else None
            if val and 500 <= val <= 500000:
                return val
        return None

    def _parse_surface(self, text: str) -> float | None:
        m = re.search(r"(\d{2,5}[\.,]?\d*)\s*m[²2]", text, re.I)
        if m:
            return float(m.group(1).replace(",", "."))
        return None
