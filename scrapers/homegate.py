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
                resp = requests.get(
                    self.API_URL,
                    params=params,
                    headers={
                        "User-Agent": self.user_agent,
                        "Accept":     "application/json",
                        "Referer":    "https://www.homegate.ch/",
                    },
                    timeout=self.timeout,
                )
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
        self.logger.info(f"[homegate] {len(listings)} annonces, {len(passed)} après filtrage")
        return passed

    def _parse_item(self, item: dict) -> dict | None:
        d = item.get("listing", item)
        uid = d.get("id", "")
        if not uid:
            return None

        url = f"https://www.homegate.ch/rent/{uid}"

        addr    = d.get("address", {})
        street  = addr.get("street", "")
        city    = addr.get("locality", "")
        district = addr.get("district", city)
        title   = clean_text(f"{street}, {city}".strip(", ")) or city

        prices    = d.get("prices", {})
        rent      = prices.get("rent", {})
        price_chf = rent.get("gross") or rent.get("net")

        chars      = d.get("characteristics", {})
        surface_m2 = chars.get("totalFloorSpace") or chars.get("livingSpace")

        loc  = d.get("localization", {})
        desc = loc.get("fr", {}).get("description", {}).get("text", "") or \
               loc.get("de", {}).get("description", {}).get("text", "") or ""

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
