from __future__ import annotations
from utils.parser import normalize, extract_possible_changing_room

def matches_criteria(listing: dict, config: dict) -> bool:
    criteria = config["criteria"]

    # --- Prix --- ne rejeter QUE si le prix est connu ET trop élevé
    price = listing.get("price_chf")
    max_price = criteria.get("max_rent_chf_month")
    if max_price is not None and price is not None:
        if price > max_price:
            return False

    # --- Surface --- ne rejeter QUE si la surface est connue ET trop petite
    surface = listing.get("surface_m2")
    min_surface = criteria.get("min_surface_m2")
    if min_surface is not None and surface is not None:
        if surface < min_surface:
            return False

    # --- Quartier ---
    combined = " ".join(filter(None, [
        listing.get("text_blob"),
        listing.get("title"),
        listing.get("location_hint"),
        listing.get("district"),
    ])).lower()

    allowed_districts = criteria.get("allowed_districts", [])
    if allowed_districts:
        allowed = [x.lower() for x in allowed_districts]
        if not any(x in combined for x in allowed):
            return False

    # --- Vestiaires ---
    if criteria.get("require_possible_changing_rooms", False):
        keywords = criteria.get("changing_room_keywords", [])
        has_changing_room = extract_possible_changing_room(combined, keywords)
        listing["possible_changing_room"] = has_changing_room
        if not has_changing_room:
            return False

    return True
