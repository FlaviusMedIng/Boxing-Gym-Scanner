from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re, time

class PiletRenaudScraper(BaseScraper):
    name = "pilet_renaud"
    use_playwright = False  # on gère Playwright manuellement ici

    BASE_URL = "https://www.pilet-renaud.ch"

    def scrape(self) -> list[dict]:
        url = self.urls[0] if self.urls else \
            "https://www.pilet-renaud.ch/fr/accueil/search/transaction/rent"

        self.logger.info(f"[pilet_renaud] Playwright → {url}")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=self.user_agent)
            page.goto(url, wait_until="networkidle", timeout=60000)
            # Attendre que les cartes soient rendues
            try:
                page.wait_for_selector(
                    "div.property, article.property, [class*='property-item'], li.property",
                    timeout=15000
                )
            except Exception:
                self.logger.warning("[pilet_renaud] Sélecteur principal absent, on parse quand même")
            time.sleep(2)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")
        results = self.parse_list_page(soup, url)
        passed  = [l for l in results if self.matches_filters(l)]
        self.logger.info(f"[pilet_renaud] {len(results)} annonces, {len(passed)} après filtrage")
        return passed

    def parse_list_page(self, soup, base_url) -> list[dict]:
        listings = []

        # Sélecteurs dans l'ordre, basés sur le HTML réel
        cards = (
            soup.select("div.property") or
            soup.select("article.property") or
            soup.select("li.property") or
            soup.select("[class*='property-item']") or
            soup.select("[class*='PropertyItem']") or
            soup.select("[class*='search-result']")
        )

        self.logger.info(f"[pilet_renaud] {len(cards)} cartes trouvées")

        if not cards:
            # Fallback : liens directs vers annonces
            return self._fallback_links(soup, base_url)

        for card in cards:
            link = card.select_one("a[href]")
            if not link:
                continue

            href = link.get("href", "")
            url  = self.absolutize(self.BASE_URL, href)

            # Titre
            title_el = (
                card.select_one(".property__title") or
                card.select_one(".property-title") or
                card.select_one("h2") or
                card.select_one("h3") or
                link
            )
            title = clean_text(title_el.get_text(" ", strip=True))

            # Prix
            price_el = (
                card.select_one(".property__price") or
                card.select_one(".property-price") or
                card.select_one("[class*='price' i]")
            )
            price_chf = self._parse_price(
                clean_text(price_el.get_text(" ", strip=True)) if price_el else ""
            )

            # Surface
            surface_el = (
                card.select_one(".property__surface") or
                card.select_one(".property-surface") or
                card.select_one("[class*='surface' i]") or
                card.select_one("[class*='area' i]")
            )
            surface_m2 = self._parse_surface(
                clean_text(surface_el.get_text(" ", strip=True)) if surface_el else ""
            )

            text_blob = clean_text(card.get_text(" ", strip=True))

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

    def _fallback_links(self, soup, base_url) -> list[dict]:
        """Dernier recours : extraire depuis les liens d'annonces."""
        listings = []
        seen = set()
        patterns = ["/annonce/", "/bien/", "/objet/", "/location/", "/rent/"]
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if not any(p in href for p in patterns):
                continue
            if href in seen:
                continue
            seen.add(href)
            url = self.absolutize(self.BASE_URL, href)
            # Remonter au conteneur parent
            parent = a
            for _ in range(6):
                parent = parent.parent
                if parent and parent.name in ("div", "article", "li", "section"):
                    if len(parent.get_text()) > 50:
                        break
            text_blob = clean_text(parent.get_text(" ", strip=True))
            listings.append(self.make_listing(
                url=url,
                title=clean_text(a.get_text(" ", strip=True))[:120],
                text_blob=text_blob,
                site=self.name,
                location_hint=text_blob,
            ))
        return listings

    def _parse_price(self, text: str) -> int | None:
        digits = re.sub(r"[^\d]", "", text)
        return int(digits) if digits else None

    def _parse_surface(self, text: str) -> float | None:
        m = re.search(r"(\d+[\.,]?\d*)", text)
        if m:
            return float(m.group(1).replace(",", "."))
        return None
