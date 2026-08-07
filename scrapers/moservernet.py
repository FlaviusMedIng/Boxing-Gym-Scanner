from scrapers.base_scraper import BaseScraper
from utils.parser import clean_text


class MoserVernetScraper(BaseScraper):

    name = "moservernet"

    use_playwright = True
    # La page a une activité réseau continue (carousels, favoris) qui
    # n'atteint jamais l'état "idle" — "networkidle" (le défaut) provoque un
    # timeout systématique à 90s. Les annonces sont déjà dans le HTML rendu
    # côté serveur, donc "domcontentloaded" suffit et est bien plus fiable.
    load_strategy = "domcontentloaded"

    urls = [
        "https://www.moservernet.ch/louer/arcades-geneve_ateliers-geneve_bureaux-geneve_surfaces-commerciales-geneve/"
    ]

    def parse_list_page(self, soup, base_url):
        listings = []

        for card in soup.select("div[data-id]"):
            link = card.select_one(".property-card__title[href]")
            # La page embarque aussi, ailleurs dans le DOM, un template
            # Mustache non rendu (utilisé côté client pour le filtrage
            # dynamique) qui matche la même structure `div[data-id]` mais
            # dont le contenu texte est littéralement "{{ property.price }}"
            # etc. — on l'ignore.
            if not link or "{{" in link.get_text():
                continue

            url = self.absolutize(base_url, link.get("href"))
            blob = clean_text(card.get_text(" ", strip=True))
            title = clean_text(link.get_text(strip=True))

            listings.append(
                self.make_listing(
                    url=url,
                    title=title,
                    text_blob=blob,
                    site=self.name,
                    location_hint=blob,
                )
            )

        return listings
