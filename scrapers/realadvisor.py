from __future__ import annotations
from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text
import re

class RealAdvisorScraper(BaseScraper):
    name = "realadvisor"
    use_playwright = True
    load_strategy = "networkidle"

    # URLs qui sont des pages de navigation, pas des annonces
    _NAV_PATTERNS = [
        "/louer/quartier-", "/louer/ville-", "/louer/canton-",
        "/louer/commercial$", "/louer/commercial/geneve",
        r"/louer/1\d{3}-",   # codes postaux ex: /louer/1227-les-acacias
    ]

    def parse_list_page(self, soup, base_url: str) -> list[dict]:
        listings = []
        seen = set()

        # Les vraies annonces RealAdvisor ont une URL type:
        # /fr/louer/commercial/NOM-ADRESSE-CODEID
        # où CODEID est un identifiant alphanum ex: MXG4-7ZER
        cards = soup.select("a[href*='/fr/louer/commercial/']")

        for link in cards:
            href = link.get("href", "")
            if not href:
                continue

            # Filtrer les liens de navigation
            if self._is_nav_url(href):
                continue

            # Une vraie annonce a un ID alphanum en fin d'URL (ex: -MXG4-7ZER)
            if not re.search(r"-[A-Z0-9]{4}-[A-Z0-9]{4}$", href):
                continue

            url = self.absolutize(base_url, href)
            if url in seen:
                continue
            seen.add(url)

            # Remonter au conteneur de la carte pour avoir tout le texte
            container = link
            for _ in range(6):
                parent = container.parent
                if not parent:
                    break
                text = parent.get_text(" ", strip=True)
                # Arrêter quand on a assez de contenu (prix + surface + desc)
                if len(text) > 200:
                    container = parent
                    break
                container = parent

            text_blob = clean_text(container.get_text(" ", strip=True))
            title = clean_text(link.get_text(" ", strip=True))[:200]

            listings.append(self.make_listing(
                url=url,
                title=title,
                text_blob=text_blob,
                site=self.name,
                location_hint=text_blob,
            ))

        return listings

    def _is_nav_url(self, href: str) -> bool:
        for pat in self._NAV_PATTERNS:
            if re.search(pat, href):
                return True
        return False
