import re
import time
import hashlib
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

# Textes de boutons couramment utilisés par les bannières de consentement
# cookies (OneTrust, Didomi, Axeptio, CMP maison, ...). On clique le premier
# bouton trouvé pour révéler le contenu de la page, comme le ferait n'importe
# quel visiteur humain — ce n'est pas un contournement de protection anti-bot.
COOKIE_BUTTON_TEXTS = [
    "Tout accepter", "Accepter tout", "Accepter et fermer", "J'accepte",
    "Accepter", "Accept all", "Accept All Cookies", "I accept", "OK",
]


class BaseScraper:
    name = "base"
    use_playwright = False
    load_strategy = "networkidle"
    max_pages = 1

    def __init__(self, site_cfg: dict, config: dict, logger):
        self.site_cfg   = site_cfg
        self.config     = config
        self.logger     = logger

        # URLs — votre config utilise "start_urls"
        self.urls = site_cfg.get("start_urls", [])

        # Pagination — nombre de pages max à parcourir par URL de départ
        self.max_pages = site_cfg.get("max_pages", self.max_pages)

        # Timeout — votre config utilise "runtime.request_timeout_seconds"
        self.timeout = config.get("runtime", {}).get("request_timeout_seconds", 30)

        # User-agent
        self.user_agent = config.get("runtime", {}).get(
            "user_agent",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        )

        # Politesse : délai entre deux requêtes (repris du site si précisé,
        # sinon valeur globale de runtime, sinon 2s par défaut)
        self.delay_seconds = site_cfg.get(
            "crawl_delay_seconds",
            config.get("runtime", {}).get("delay_between_requests_seconds", 2)
        )
        self.max_retries = config.get("runtime", {}).get("max_retries", 2)

        # Playwright global
        self.use_playwright = (
            self.use_playwright
            or config.get("runtime", {}).get("use_playwright_for_dynamic_sites", False)
        )

    # ------------------------------------------------------------------ #
    #  Fetch                                                               #
    # ------------------------------------------------------------------ #

    def fetch_html(self, url: str) -> str:
        last_exc = None
        for attempt in range(1, self.max_retries + 2):
            try:
                if self.use_playwright:
                    return self._fetch_playwright(url)
                return self._fetch_requests(url)
            except Exception as exc:
                last_exc = exc
                if attempt <= self.max_retries:
                    wait = 3 * attempt
                    self.logger.warning(
                        f"[{self.name}] Tentative {attempt} échouée sur {url} "
                        f"({exc}), nouvel essai dans {wait}s"
                    )
                    time.sleep(wait)
        raise last_exc

    def _fetch_requests(self, url: str) -> str:
        r = requests.get(
            url,
            timeout=self.timeout,
            headers={"User-Agent": self.user_agent}
        )
        r.raise_for_status()
        return r.text

    def _dismiss_cookie_banner(self, page) -> None:
        for text in COOKIE_BUTTON_TEXTS:
            try:
                button = page.get_by_role("button", name=text, exact=False)
                if button.count() > 0:
                    button.first.click(timeout=2000)
                    page.wait_for_timeout(500)
                    return
            except Exception:
                continue

    def _fetch_playwright(self, url: str) -> str:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=self.user_agent)
            page.goto(
                url,
                wait_until=self.load_strategy,
                timeout=self.timeout * 1000
            )
            self._dismiss_cookie_banner(page)
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
        import hashlib
        from utils.parser import (
            compute_monthly_rent, parse_surface_m2,
            detect_district, extract_possible_changing_room
        )
        criteria = self.config.get("criteria", {})
        keywords = criteria.get("changing_room_keywords", [])
        combined = " ".join(filter(None, [text_blob, title, location_hint]))
    
        # Normaliser le prix en CHF/mois depuis n'importe quelle unité
        if price_chf is None:
            price_chf = compute_monthly_rent(combined, surface_m2)
        
        # Si on a le prix mais pas la surface, tenter de parser la surface
        if surface_m2 is None:
            surface_m2 = parse_surface_m2(combined)
        
        # Recalculer avec la surface si le premier essai a échoué
        if price_chf is None and surface_m2 is not None:
            price_chf = compute_monthly_rent(combined, surface_m2)
    
        district = detect_district(combined)
        possible_changing_room = extract_possible_changing_room(combined, keywords)
    
        return {
            "id":                    hashlib.md5((url or "").encode()).hexdigest(),
            "url":                   url,
            "title":                 title,
            "price_chf":             price_chf,
            "surface_m2":            surface_m2,
            "rooms":                 rooms,
            "text_blob":             text_blob,
            "location_hint":         location_hint,
            "district":              district,
            "possible_changing_room": possible_changing_room,
            "site":                  site or self.name,
        }
    
    # ------------------------------------------------------------------ #
    #  Scrape principal                                                    #
    # ------------------------------------------------------------------ #
    #  Le filtrage (prix/surface/quartier/vestiaires) et le score sont
    #  calculés une seule fois, de façon centralisée, dans main.py
    #  (filters/gym_filter.py + scoring/gym_score.py). Les scrapers ne
    #  font que renvoyer les annonces brutes qu'ils ont trouvées.
    # ------------------------------------------------------------------ #

    def scrape(self) -> list[dict]:
        listings = []
        for start_url in self.urls:
            seen_urls_for_start: set[str] = set()
            for page_num in range(1, self.max_pages + 1):
                page_url = start_url if page_num == 1 else self.build_page_url(start_url, page_num)
                if not page_url:
                    break

                self.logger.info(f"[{self.name}] Fetching {page_url}")
                try:
                    html = self.fetch_html(page_url)
                    soup = BeautifulSoup(html, "html.parser")
                    results = self.parse_list_page(soup, page_url)
                except Exception as e:
                    self.logger.error(f"[{self.name}] Erreur sur {page_url}: {e}")
                    break

                new_results = [r for r in results if r.get("url") not in seen_urls_for_start]
                self.logger.info(
                    f"[{self.name}] page {page_num}: {len(results)} annonces "
                    f"({len(new_results)} nouvelles)"
                )
                listings.extend(new_results)
                seen_urls_for_start.update(r.get("url") for r in new_results)

                if not new_results:
                    # Page vide ou identique à la précédente : plus rien à paginer
                    break

                if page_num < self.max_pages:
                    time.sleep(self.delay_seconds)

        return listings

    def build_page_url(self, start_url: str, page_num: int) -> str | None:
        """À surcharger par site pour construire l'URL de la page N (N >= 2).
        Retourne None si le site ne supporte pas / n'a pas besoin de pagination."""
        return None

    def parse_list_page(self, soup, base_url) -> list[dict]:
        raise NotImplementedError
