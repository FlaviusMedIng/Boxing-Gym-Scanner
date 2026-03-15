from __future__ import annotations


def compute_score(listing: dict, config: dict) -> int:
    score = 0
    surface = listing.get("surface_m2") or 0
    price = listing.get("price_chf_month") or 999999
    district = (listing.get("district") or listing.get("location_text") or "").lower()
    raw = (listing.get("raw_text") or "").lower()

    if surface >= 200:
        score += 35
    elif surface >= 120:
        score += 25
    elif surface >= 70:
        score += 15

    if price <= 1200:
        score += 30
    elif price <= 1600:
        score += 22
    elif price <= 2000:
        score += 15

    if any(x in district for x in ["plainpalais", "eaux-vives", "champel", "rive", "rives", "jonction"]):
        score += 20

    if listing.get("possible_changing_room"):
        score += 10

    if any(x in raw for x in ["rez", "rez-de-chaussée", "arcade", "ground floor", "vitrine"]):
        score += 5

    return min(score, 100)
