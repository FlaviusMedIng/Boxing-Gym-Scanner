from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text


class HomegateScraper(BaseScraper):

    name = "homegate"
    use_playwright = True
    load_strategy = "domcontentloaded"

    def parse_list_page(self, soup, base_url):

        listings = []

        cards = soup.select("a[data-testid='listing-link']")

        for link in cards:

            href = link.get("href")

            if not href:
                continue

            url = self.absolutize(base_url, href)

            text_blob = clean_text(link.parent.get_text(" ", strip=True))
            title = clean_text(link.get_text())

            listings.append(
                {
                    "url": url,
                    "title": title,
                    "text_blob": text_blob,
                    "site": self.name
                }
            )

        return listings
