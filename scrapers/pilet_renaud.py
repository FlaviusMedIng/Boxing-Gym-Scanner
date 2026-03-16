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
            # Ignorer les ressources inutiles pour accélérer
            page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf}", 
                       lambda r: r.abort())
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            # Attendre que le contenu JS soit rendu
            time.sleep(5)
            html = page.content()
            browser.close()

        soup = BeautifulSoup(html, "html.parser")
        results = self.parse_list_page(soup, url)
        passed  = [l for l in results if self.matches_filters(l)]
        self.logger.info(
            f"[pilet_renaud] {len(results)} annonces, {len(passed)} après filtrage"
        )
        return passed

    def parse_list_page(self, soup, base_url) -> list[dict]:
        listings = []

        # Sélecteurs basés sur le HTML réel de pilet-renaud.ch
        cards = (
            soup.select("div.propitem") or
            soup.select("div.prop-item") or
            soup.select("div.property-item") or
            soup.select("[class*='propitem']") or
            soup.select("[class*='prop_item']") or
            soup.select("[class*='listing-item']")
        )

        self.logger.info(f"[pilet_renaud] {len(cards)} cartes trouvées")

        if not cards:
            return self._fallback_links(soup)

        for card in cards:
            link = card.select_one("a[href]")
            if not link:
                continue

            href = link.get("href", "")
            url  = self.absolutize(self.BASE_URL, href)

            title_el = (
                card.select_one(".propitem__title") or
                card.select_one(".prop-item__title") or
                card.select_one(".property__title") or
                card.select_one("h2") or
                card.select_one("h3") or
                link
            )
            title = clean_text(title_el.get_text(" ", strip=True))

            price_el = (
                card.select_one(".propitem__price") or
                card.select_one(".prop-item__price") or
                card.select_one("[class*='price']")
            )
            price_chf = self._parse_price(
                clean_text(price_el.get_text(" ", strip=True)) if price_el else ""
            )

            surface_el = (
                card.select_one(".propitem__surface") or
                card.select_one(".prop-item__surface") or
                card.select_one("[class*='surface']") or
                card.select_one("[class*='area']")
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

    def _fallback_links(self, soup) -> list[dict]:
        listings = []
        seen = set()
        for a in soup.select("a[href*='/fr/'], a[href*='/annonce'], a[href*='/bien']"):
            href = a.get("href", "")
            # Filtrer les liens de navigation
            if len(href) < 20 or href in seen:
                continue
            text = a.get_text(" ", strip=True)
            if len(text) < 5:
                continue
            seen.add(href)
            url = self.absolutize(self.BASE_URL, href)
            parent = a
            for _ in range(6):
                parent = parent.parent
                if parent and parent.name in ("div", "article", "li") \
                        and len(parent.get_text()) > 30:
                    break
            text_blob = clean_text(parent.get_text(" ", strip=True))
            listings.append(self.make_listing(
                url=url,
                title=clean_text(text)[:120],
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
