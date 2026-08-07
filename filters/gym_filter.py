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

    # --- Type de bien ---
    # Comparaison sur le champ structuré (déjà déterminé une fois par
    # detect_property_type, insensible aux accents/casse) plutôt qu'une
    # recherche de sous-chaîne dans le texte brut comme pour le quartier —
    # le vocabulaire est fermé (PROPERTY_TYPES), donc pas besoin de la
    # tolérance qu'offre le texte libre, et ça évite un mismatch d'accents
    # entre le libellé du critère ("Dépôt") et le texte source ("depot").
    allowed_property_types = criteria.get("allowed_property_types", [])
    if allowed_property_types:
        property_type = listing.get("property_type")
        if property_type and property_type not in allowed_property_types:
            return False

    # --- Vestiaires ---
    if criteria.get("require_possible_changing_rooms", False):
        keywords = criteria.get("changing_room_keywords", [])
        has_changing_room = extract_possible_changing_room(combined, keywords)
        listing["possible_changing_room"] = has_changing_room
        if not has_changing_room:
            return False

    return True
