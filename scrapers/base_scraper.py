from __future__ import annotations

import hashlib
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from utils.browser import fetch_dynamic_html
from utils.parser import (
    clean_text,
    detect_district,
    extract_possible_changing_room,
    parse_price_chf_month,
    parse_surface_m2,
)


class BaseScraper:
    name = "base"
    use_playwright = False

    def __init__(self, site_config: dict, global_config: dict, logger):
        self.site_config = site_config
        self.global_config = global_config
        self.logger = logger
        self.timeout = int(global_config["runtime"]["request_timeout_seconds"])
        self.user_agent = global_config["runtime"]["user_agent"]

    def fetch_html(self, url: str) -> str:
        if self.use_playwright and self.global_config["runtime"].get("use_playwright_for_dynamic_sites", True):
            return fetch_dynamic_html(url, timeout_ms=self.timeout * 1000)
        response = requests.get(url, timeout=self.timeout, headers={"User-Agent": self.user_agent})
        response.raise_for_status()
        return response.text

    def start_urls(self) -> list[str]:
        return list(self.site_config.get("start_urls", []))

    def scrape(self) -> list[dict]:
        results: list[dict] = []
        for url in self.start_urls():
            html = self.fetch_html(url)
            soup = BeautifulSoup(html, "html.parser")
            results.extend(self.parse_list_page(soup, base_url=url))
        return results

    def parse_list_page(self, soup: BeautifulSoup, base_url: str) -> list[dict]:
        raise NotImplementedError

    def make_listing(self, *, url: str, title: str, text_blob: str, site: str, location_hint: str = "") -> dict:
        url = url.strip()
        full_text = clean_text(" ".join([title, text_blob, location_hint]))
        price = parse_price_chf_month(full_text)
        surface = parse_surface_m2(full_text)
        district = detect_district(full_text)
        possible_changing_room = extract_possible_changing_room(
            full_text,
            self.global_config["criteria"].get("changing_room_keywords", []),
        )
        listing_id = hashlib.sha1(f"{site}|{url}".encode("utf-8")).hexdigest()
        return {
            "id": listing_id,
            "site": site,
            "title": clean_text(title)[:300],
            "description": clean_text(text_blob)[:4000],
            "url": url,
            "price_chf_month": price,
            "surface_m2": surface,
            "district": district,
            "location_text": clean_text(location_hint),
            "possible_changing_room": possible_changing_room,
            "raw_text": full_text[:8000],
        }

    @staticmethod
    def absolutize(base_url: str, url: str | None) -> str:
        return urljoin(base_url, url or "")
