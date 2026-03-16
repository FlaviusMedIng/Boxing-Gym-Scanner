import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

class BaseScraper:
    name = "base"
    use_playwright = False
    load_strategy = "networkidle"

    def __init__(self, site_cfg: dict, config: dict, logger):
        self.site_cfg   = site_cfg
        self.config     = config
        self.logger     = logger
        self.urls       = site_cfg.get("urls", [])
        self.timeout    = config.get("timeout", 20)
        self.user_agent = config.get(
            "user_agent",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        )
        # Critères de filtrage lus depuis la config globale
        self.max_price    = config.get("filters", {}).get("max_price")
        self.min_surface  = config.get("filters", {}).get("min_surface")

    # ------------------------------------------------------------------ #
    #  Fetch                                                               #
    # ------------------------------------------------------------------ #

    def fetch_html(self, url: str) -> str:
        if self.use_playwright:
            return self._fetch_playwright(url)
        return self._fetch_requests(url)

    def _fetch_requests(self, url: str) -> str:
        r = requests.get(
            url,
            timeout=self.timeout,
            headers={"User-Agent": self.user_agent}
        )
        r.raise_for_status()
        return r.text

    def _fetch_playwright(self, url: str) -> str:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=self.user_agent)
            page.goto(url, wait_until=self.load_strategy, timeout=self.timeout * 1000)
            html = page.content()
            browser.close()
        return html

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def absolutize(self, base: str, href: str) -> str:
        return urljoin(base, href)

    def make_listing(self, url, title=None, price_chf=None,
                     surface_m2=None, rooms=None,
                     text_blob=None, site=None, location_hint=None) -> dict:
        return {
            "url":          url,
            "title":        title,
            "price_chf":    price_chf,
            "surface_m2":   surface_m2,
            "rooms":        rooms,
            "text_blob":    text_blob,
            "location_hint": location_hint,
            "site":         site or self.name,
        }

    def matches_filters(self, listing: dict) -> bool:
        """Retourne True si l'annonce passe les filtres prix/surface."""
        if self.max_price is not None:
            price = listing.get("price_chf")
            if price is not None and price > self.max_price:
                return False
        if self.min_surface is not None:
            surface = listing.get("surface_m2")
            if surface is not None and surface < self.min_surface:
                return False
        return True

    # ------------------------------------------------------------------ #
    #  Scrape principal                                                    #
    # ------------------------------------------------------------------ #

    def scrape(self) -> list[dict]:
        listings = []
        for url in self.urls:
            self.logger.info(f"[{self.name}] Fetching {url}")
            try:
                html = self.fetch_html(url)
                soup = BeautifulSoup(html, "html.parser")
                results = self.parse_list_page(soup, url)
                passed = [r for r in results if self.matches_filters(r)]
                self.logger.info(
                    f"[{self.name}] {len(results)} annonces trouvées, "
                    f"{len(passed)} après filtrage"
                )
                listings.extend(passed)
            except Exception as e:
                self.logger.error(f"[{self.name}] Erreur sur {url}: {e}")
        return listings

    def parse_list_page(self, soup, base_url) -> list[dict]:
        raise NotImplementedError
