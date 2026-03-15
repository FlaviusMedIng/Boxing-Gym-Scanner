import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.rosset.ch/location/locaux-commerciaux/all/geneve/"

def scrape():

    listings = []

    for page in range(1,6):

        url = f"{BASE_URL}?page_no={page}"

        r = requests.get(url, timeout=30)

        if r.status_code != 200:
            break

        soup = BeautifulSoup(r.text,"html.parser")

        cards = soup.select("article")

        if not cards:
            break

        for c in cards:

            link = c.find("a")

            if not link:
                continue

            title = c.get_text(strip=True)

            listings.append({

                "id": "rosset_"+link["href"],
                "title": title,
                "price": 0,
                "surface": 0,
                "location": "Geneve",
                "url": link["href"],
                "site": "rosset"

            })

    return listings
