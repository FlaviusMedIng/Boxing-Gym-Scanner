from __future__ import annotations
from utils.parser import normalize, extract_possible_changing_room

def matches_criteria(listing: dict, config: dict) -> bool:
    criteria = config["criteria"]

    # --- Prix ---
    price = listing.get("price_chf")                    # ← était price_chf_month
    max_price = criteria.get("max_rent_chf_month")
    if max_price is not None:
        if price is None or price > max_price:
            return False

    # --- Surface ---
    surface = listing.get("surface_m2")
    min_surface = criteria.get("min_surface_m2")
    if min_surface is not None:
        if surface is None or surface < min_surface:
            return False

    # --- Quartier ---
    combined = (
        (listing.get("text_blob") or "") + " " +
        (listing.get("title") or "") + " " +
        (listing.get("location_hint") or "")
    ).lower()

    allowed_districts = criteria.get("allowed_districts", [])
    if allowed_districts:
        allowed = [x.lower() for x in allowed_districts]
        if not any(x in combined for x in allowed):
            return False

    # --- Vestiaires ---
    if criteria.get("require_possible_changing_rooms", False):
        keywords = criteria.get("changing_room_keywords", [])
        has_changing_room = extract_possible_changing_room(combined, keywords)
        listing["possible_changing_room"] = has_changing_room  # enrichit le listing
        if not has_changing_room:
            return False

    return True
