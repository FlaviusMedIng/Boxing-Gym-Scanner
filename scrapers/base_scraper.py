import re
import hashlib
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

        # URLs — votre config utilise "start_urls"
        self.urls = site_cfg.get("start_urls", [])

        # Timeout — votre config utilise "runtime.request_timeout_seconds"
        self.timeout = config.get("runtime", {}).get("request_timeout_seconds", 30)

        # User-agent
        self.user_agent = config.get("runtime", {}).get(
            "user_agent",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        )

        # Playwright global
        self.use_playwright = (
            self.use_playwright
            or config.get("runtime", {}).get("use_playwright_for_dynamic_sites", False)
        )

        # Critères — votre config utilise "criteria"
        criteria = config.get("criteria", {})
        self.max_price   = criteria.get("max_rent_chf_month")
        self.min_surface = criteria.get("min_surface_m2")
        self.allowed_districts   = [
            d.lower() for d in criteria.get("allowed_districts", [])
        ]
        self.changing_room_keywords = [
            k.lower() for k in criteria.get("changing_room_keywords", [])
        ]
        self.require_changing_rooms = criteria.get("require_possible_changing_rooms", False)
        self.floors_preferred = [
            f.lower() for f in criteria.get("floors_preferred", [])
        ]

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
            page.goto(
                url,
                wait_until=self.load_strategy,
                timeout=self.timeout * 1000
            )
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
    #  Filtrage                                                            #
    # ------------------------------------------------------------------ #

    def matches_filters(self, listing: dict) -> bool:
        blob = (listing.get("text_blob") or "").lower()
        title = (listing.get("title") or "").lower()
        combined = blob + " " + title

        # Prix
        if self.max_price is not None:
            price = listing.get("price_chf")
            if price is not None and price > self.max_price:
                return False

        # Surface
        if self.min_surface is not None:
            surface = listing.get("surface_m2")
            if surface is not None and surface < self.min_surface:
                return False

        # Quartier — si la liste est définie, au moins un doit matcher
        if self.allowed_districts:
            if not any(d in combined for d in self.allowed_districts):
                return False

        # Vestiaires / local aménageable
        if self.require_changing_rooms:
            if not any(kw in combined for kw in self.changing_room_keywords):
                return False

        return True

    def score_listing(self, listing: dict) -> int:
        """Score de pertinence 0-10 pour trier les résultats."""
        score = 0
        blob = (listing.get("text_blob") or "").lower()
        combined = blob + " " + (listing.get("title") or "").lower()

        # Présence de mots-clés vestiaires
        kw_hits = sum(1 for kw in self.changing_room_keywords if kw in combined)
        score += min(kw_hits * 2, 6)

        # Étage préféré
        if any(f in combined for f in self.floors_preferred):
            score += 2

        # Quartier exact
        if any(d in combined for d in self.allowed_districts):
            score += 2

        return min(score, 10)

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

                passed = []
                for r in results:
                    if self.matches_filters(r):
                        r["score"] = self.score_listing(r)
                        passed.append(r)

                self.logger.info(
                    f"[{self.name}] {len(results)} annonces, "
                    f"{len(passed)} après filtrage"
                )
                listings.extend(passed)

            except Exception as e:
                self.logger.error(f"[{self.name}] Erreur sur {url}: {e}")

        return listings

    def parse_list_page(self, soup, base_url) -> list[dict]:
        raise NotImplementedError
