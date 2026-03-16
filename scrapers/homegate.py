import requests

from scrapers.base_scraper import BaseScraper


class HomegateScraper(BaseScraper):

    name = "homegate"

    use_playwright = False

    def scrape(self):

        listings = []

        url = "https://api.homegate.ch/search/listings"

        params = {
            "location": "geneve",
            "category": "commercial"
        }

        r = requests.get(url, params=params)

        if r.status_code != 200:
            return listings

        data = r.json()

        for item in data.get("results", []):

            listings.append(
                {
                    "id": item.get("id"),
                    "title": item.get("title"),
                    "rent_chf": item.get("price"),
                    "surface_m2": item.get("livingSpace"),
                    "location": item.get("address"),
                    "url": "https://www.homegate.ch" + item.get("detailUrl", ""),
                    "site": "homegate"
                }
            )

        return listings
