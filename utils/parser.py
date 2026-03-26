from __future__ import annotations
import re
import unicodedata

DISTRICTS = [
    "Champel", "Eaux-Vives", "Rive", "Rives",
    "Plainpalais", "Jonction", "Carouge", "Acacias",
]

def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()

def normalize(value: str | None) -> str:
    value = clean_text(value).lower()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return value

def _extract_number(text: str) -> int | None:
    """
    Extrait un nombre depuis un texte suisse.
    Gère: "8'646", "8 646", "8.646", "8646", "1'246.50"
    Retourne None si rien trouvé ou valeur hors plage raisonnable.
    """
    # Supprimer les séparateurs de milliers suisses ' et espaces entre chiffres
    # Ex: "8'646" → "8646", "1'246.50" → garde seulement la partie entière
    t = text.strip()
    # Chercher un pattern: chiffres avec séparateurs optionnels
    m = re.search(r"(\d[\d''\s]*(?:[.,]\d{3})*(?:[.,]\d{1,2})?)", t)
    if not m:
        return None
    raw = m.group(1)
    # Supprimer séparateurs de milliers (', ', espace entre 3 chiffres)
    raw = re.sub(r"['\s](?=\d{3}(?!\d))", "", raw)
    # Supprimer virgule/point décimal finale
    raw = re.sub(r"[.,]\d{1,2}$", "", raw)
    raw = re.sub(r"[^\d]", "", raw)
    return int(raw) if raw else None

def parse_price_chf_month(text: str | None) -> int | None:
    """
    Retourne toujours un prix en CHF/mois, quelle que soit l'unité source.
    Gère: CHF/mois, CHF/m²/an, CHF/an
    """
    if not text:
        return None
    t = normalize(text)

    # --- CHF/m²/an → besoin de la surface pour convertir ---
    # On ne peut pas convertir sans surface, on retourne None
    # (géré dans compute_monthly_rent)

    # --- CHF/mois explicite ---
    patterns_monthly = [
        r"chf\s*([\d''\s]+)\s*/?\s*(?:mois|month|mo\.?)",
        r"([\d''\s]+)\s*chf\s*/?\s*(?:mois|month)",
        r"loyer\s*(?:mensuel)?\s*chf\s*([\d''\s]+)",
        r"loyer[^\d]{0,20}([\d''\s]{3,})",
        # Format carte: "CHF 2'245.-" sans unité explicite
        r"chf\s*([\d''\s]+)[.\-–]",
    ]
    for pat in patterns_monthly:
        m = re.search(pat, t, re.I)
        if m:
            val = _extract_number(m.group(1))
            if val and 300 <= val <= 100000:
                return val

    # --- Montant seul avec CHF (pas de /m²) ---
    # Éviter les prix/m²/an qui ont "m2" ou "m²" dans les 20 chars suivants
    m = re.search(r"chf\s*([\d''\s]{3,})", t)
    if m:
        # Vérifier que ce n'est pas un prix/m²
        context_after = t[m.end():m.end()+30]
        if not re.search(r"m[²2²]", context_after):
            val = _extract_number(m.group(1))
            if val and 300 <= val <= 100000:
                return val

    return None

def parse_price_m2_year(text: str | None) -> float | None:
    """Extrait CHF/m²/an depuis le texte."""
    if not text:
        return None
    t = normalize(text)
    patterns = [
        r"chf\s*([\d''\s]+)\s*/?\s*m[²2²]\s*/?\s*(?:an|year|yr)",
        r"([\d''\s]+)\s*chf\s*/?\s*m[²2²]\s*/?\s*(?:an|year)",
        r"([\d''\s]+)\s*/?\s*m[²2²]\s*/?\s*(?:an|year|yr)",
    ]
    for pat in patterns:
        m = re.search(pat, t)
        if m:
            val = _extract_number(m.group(1))
            if val and 50 <= val <= 5000:
                return float(val)
    return None

def parse_price_year(text: str | None) -> int | None:
    """Extrait CHF/an (sans /m²)."""
    if not text:
        return None
    t = normalize(text)
    m = re.search(r"chf\s*([\d''\s]+)\s*/?\s*(?:an|year|yr)(?!\s*/?\s*m)", t)
    if m:
        val = _extract_number(m.group(1))
        if val and 1000 <= val <= 2000000:
            return val
    return None

def compute_monthly_rent(text: str | None, surface_m2: float | None = None) -> int | None:
    """
    Retourne le loyer mensuel en CHF, en normalisant depuis n'importe quelle unité.
    Priorité: CHF/mois > CHF/an /12 > CHF/m²/an * surface /12
    """
    if not text:
        return None

    # 1. CHF/mois direct
    monthly = parse_price_chf_month(text)
    if monthly:
        return monthly

    # 2. CHF/an → /12
    yearly = parse_price_year(text)
    if yearly:
        return yearly // 12

    # 3. CHF/m²/an * surface / 12
    m2_year = parse_price_m2_year(text)
    if m2_year and surface_m2:
        return int((m2_year * surface_m2) / 12)

    return None

def parse_surface_m2(text: str | None) -> float | None:
    if not text:
        return None
    t = normalize(text).replace(",", ".")
    patterns = [
        r"(\d{2,5}(?:\.\d+)?)\s*m[²2²]",
        r"surface[^\d]{0,20}(\d{2,5}(?:\.\d+)?)",
        r"(\d{2,5}(?:\.\d+)?)\s*m2",
    ]
    for pat in patterns:
        m = re.search(pat, t)
        if m:
            try:
                val = float(m.group(1))
                if 20 <= val <= 10000:
                    return val
            except ValueError:
                continue
    return None

def detect_district(text: str | None) -> str | None:
    t = normalize(text)
    for district in DISTRICTS:
        if normalize(district) in t:
            return district
    return None

def extract_possible_changing_room(text: str | None, keywords: list[str]) -> bool:
    t = normalize(text)
    return any(normalize(word) in t for word in keywords)
