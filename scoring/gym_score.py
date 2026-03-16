from __future__ import annotations

def compute_score(listing: dict, config: dict) -> int:
    score = 0

    surface = listing.get("surface_m2") or 0
    price   = listing.get("price_chf") or 999999        # ← était price_chf_month
    combined = (
        (listing.get("text_blob") or "") + " " +        # ← était raw_text
        (listing.get("title") or "") + " " +
        (listing.get("location_hint") or "")
    ).lower()

    # Surface
    if surface >= 200:
        score += 35
    elif surface >= 120:
        score += 25
    elif surface >= 70:
        score += 15

    # Prix
    if price <= 1200:
        score += 30
    elif price <= 1600:
        score += 22
    elif price <= 2000:
        score += 15

    # Quartier
    quartiers = ["plainpalais", "eaux-vives", "champel", "rive", "rives", "jonction"]
    if any(q in combined for q in quartiers):
        score += 20

    # Vestiaires / local aménageable
    if listing.get("possible_changing_room"):
        score += 10

    # Rez-de-chaussée / arcade
    if any(x in combined for x in ["rez", "rez-de-chaussee", "arcade", "ground floor", "vitrine"]):
        score += 5

    return min(score, 100)
