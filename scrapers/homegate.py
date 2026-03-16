from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text
import requests
import re

class HomegateScraper(BaseScraper):
    name = "homegate"
    use_playwright = False

    API_URL = "https://api.homegate.ch/search/listingswithads"

    def scrape(self) -> list[dict]:
        listings = []
        page = 1

        session = requests.Session()
        # Simuler une vraie session navigateur pour éviter le 403
        session.headers.update({
            "User-Agent":      self.user_agent,
            "Accept":          "application/json, text/plain, */*",
            "Accept-Language": "fr-CH,fr;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer":         "https://www.homegate.ch/",
            "Origin":          "https://www.homegate.ch",
            "Connection":      "keep-alive",
            "Sec-Fetch-Dest":  "empty",
            "Sec-Fetch-Mode":  "cors",
            "Sec-Fetch-Site":  "same-site",
        })

        # Visiter d'abord la page principale pour obtenir les cookies
        try:
            session.get(
                "https://www.homegate.ch/rent/industrial-object/city-geneva/matching-list",
                timeout=self.timeout,
                allow_redirects=True,
            )
        except Exception as e:
            self.logger.warning(f"[homegate] Pré-visite échouée (non bloquant): {e}")

        while True:
            params = {
                "offerType":     "rent",
                "categories[]":  "INDUSTRIAL_OBJECT",
                "locationIds[]": "city-8660400",
                "pageSize":      20,
                "pageNumber":    page,
                "sortBy":        "dateCreated",
                "sortDirection": "desc",
            }
            try:
                resp = session.get(
                    self.API_URL,
                    params=params,
                    timeout=self.timeout,
                )
                self.logger.info(f"[homegate] API status: {resp.status_code}")
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                self.logger.error(f"[homegate] API erreur page {page}: {e}")
                break

            items = data.get("listings") or data.get("results") or []
            if not items:
                break

            for item in items:
                parsed = self._parse_item(item)
                if parsed:
                    listings.append(parsed)

            total = data.get("total", 0)
            self.logger.info(f"[homegate] Page {page}: {len(items)} / {total}")
            if page * 20 >= total:
                break
            page += 1

        passed = [l for l in listings if self.matches_filters(l)]
        self.logger.info(
            f"[homegate] {len(listings)} annonces, {len(passed)} après filtrage"
        )
        return passed

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
