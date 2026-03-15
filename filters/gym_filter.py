from __future__ import annotations


def matches_criteria(listing: dict, config: dict) -> bool:
    criteria = config["criteria"]

    price = listing.get("price_chf_month")
    if price is None or price > criteria["max_rent_chf_month"]:
        return False

    surface = listing.get("surface_m2")
    if surface is None or surface < criteria["min_surface_m2"]:
        return False

    district = (listing.get("district") or listing.get("location_text") or "").lower()
    if criteria.get("allowed_districts"):
        allowed = [x.lower() for x in criteria["allowed_districts"]]
        if not any(x in district for x in allowed):
            return False

    if criteria.get("require_possible_changing_rooms", False):
        if not listing.get("possible_changing_room", False):
            return False

    return True
