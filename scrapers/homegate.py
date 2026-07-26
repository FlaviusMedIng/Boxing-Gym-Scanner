from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re, time, json

class HomegateScraper(BaseScraper):
    name = "homegate"
    use_playwright = False
    BASE_URL = "https://www.homegate.ch"

    def scrape(self) -> list[dict]:
        url = self.urls[0] if self.urls else \
            "https://www.homegate.ch/rent/industrial-object/city-geneva/matching-list"

        self.logger.info(f"[homegate] Playwright+intercept → {url}")
        api_responses = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=self.user_agent,
                locale="fr-CH",
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()

            # Intercepter les réponses JSON de l'API interne
            def handle_response(response):
                if "api.homegate.ch" in response.url and response.status == 200:
                    try:
                        data = response.json()
                        if data.get("listings") or data.get("results"):
                            api_responses.append(data)
                            self.logger.info(
                                f"[homegate] API interceptée: {response.url[:80]}"
                            )
                    except Exception:
                        pass

            page.on("response", handle_response)
            page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf}",
                       lambda r: r.abort())

            page.goto(url, wait_until="domcontentloaded", timeout=90000)
            time.sleep(6)  # laisser les appels XHR se terminer
            html = page.content()
            browser.close()

        # Si on a intercepté des données API — chemin optimal
        if api_responses:
            self.logger.info(
                f"[homegate] {len(api_responses)} réponses API interceptées"
            )
            listings = []
            for data in api_responses:
                for item in (data.get("listings") or data.get("results") or []):
                    parsed = self._parse_item(item)
                    if parsed:
                        listings.append(parsed)
        else:
            # Fallback : parser le HTML rendu
            self.logger.warning(
                "[homegate] Aucune API interceptée, fallback HTML"
            )
            soup = BeautifulSoup(html, "html.parser")
            listings = self.parse_list_page(soup, url)

        self.logger.info(f"[homegate] {len(listings)} annonces trouvées")
        return listings

    def _parse_item(self, item: dict) -> dict | None:
        d = item.get("listing", item)
        uid = d.get("id", "")
        if not uid:
            return None

        url      = f"https://www.homegate.ch/rent/{uid}"
        addr     = d.get("address", {})
        street   = addr.get("street", "")
        city     = addr.get("locality", "")
        district = addr.get("district", city)
        title    = clean_text(f"{street}, {city}".strip(", ")) or city

        prices    = d.get("prices", {})
        rent      = prices.get("rent", {})
        price_chf = rent.get("gross") or rent.get("net")

        chars      = d.get("characteristics", {})
        surface_m2 = chars.get("totalFloorSpace") or chars.get("livingSpace")

        loc  = d.get("localization", {})
        desc = (loc.get("fr", {}).get("description", {}).get("text") or
                loc.get("de", {}).get("description", {}).get("text") or "")

        text_blob = clean_text(f"{title} {desc} {district}")

        return self.make_listing(
            url=url,
            title=title,
            price_chf=int(price_chf) if price_chf else None,
            surface_m2=float(surface_m2) if surface_m2 else None,
            text_blob=text_blob,
            site=self.name,
            location_hint=f"{district} {city}",
        )

    def parse_list_page(self, soup, base_url) -> list[dict]:
        """Fallback HTML si l'interception API échoue."""
        listings = []
        cards = (
            soup.select('div[data-test="result-list-item"]') or
            soup.select('[class*="ResultList_listItem"]') or
            soup.select('[class*="listing-item"]')
        )
        for card in cards:
            link = card.select_one("a[href]")
            if not link:
                continue
            url       = self.absolutize(self.BASE_URL, link.get("href", ""))
            text_blob = clean_text(card.get_text(" ", strip=True))
            listings.append(self.make_listing(
                url=url,
                title=text_blob[:120],
                text_blob=text_blob,
                site=self.name,
                location_hint=text_blob,
            ))
        return listings
