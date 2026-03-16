from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text


class HomegateScraper(BaseScraper):

    name = "homegate"
    use_playwright = True
    load_strategy = "domcontentloaded"

    def parse_list_page(self, soup, base_url):

        listings = []
    
        cards = soup.select("a[href*='/rent/'][class]")
    
        for card in cards:
    
            href = card.get("href")
    
            if not href:
                continue
    
            url = self.absolutize(base_url, href)
    
            text_blob = clean_text(card.get_text(" ", strip=True))
    
            title = text_blob[:120]
    
            listings.append(
                self.make_listing(
                    url=url,
                    title=title,
                    text_blob=text_blob,
                    site=self.name,
                    location_hint=text_blob
                )
            )
    
        return listings
