from __future__ import annotations
import re
import unicodedata

DISTRICTS = [
    "Champel", "Eaux-Vives", "Rive", "Rives",
    "Plainpalais", "Jonction", "Carouge", "Acacias",
    # Ajoutés le 2026-08-07 pour élargir le périmètre de recherche (gare
    # Cornavin et quartiers centraux voisins) : le père du user filtre
    # ensuite lui-même via le site (dropdown quartier) ou docs/criteria.html.
    "Cornavin", "Pâquis", "Servette", "Grottes", "Petit-Saconnex", "Charmilles",
]

# NPA (codes postaux) de la Ville de Genève vers quartier. Beaucoup d'annonces
# mentionnent uniquement le NPA (ex: "1206 Genève") et jamais le nom du quartier
# en toutes lettres, ce qui les faisait passer à travers le filtre par quartier.
# Mapping volontairement restreint aux NPA sans ambiguïté raisonnable.
NPA_TO_DISTRICT = {
    "1201": "Cornavin",
    "1205": "Plainpalais",
    "1206": "Champel",
    "1207": "Eaux-Vives",
    "1208": "Eaux-Vives",
}

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
    m = re.search(r"(\d[\d'’\s]*(?:[.,]\d{3})*(?:[.,]\d{1,2})?)", t)
    if not m:
        return None
    raw = m.group(1)
    # Supprimer séparateurs de milliers (', ', espace entre 3 chiffres)
    raw = re.sub(r"['’\s](?=\d{3}(?!\d))", "", raw)
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
    # Le pattern générique "CHF ###.-" sans unité explicite est délibérément
    # exclu de cette liste : sans vérifier qu'il n'est pas suivi de "/m²/an",
    # il confond systématiquement un prix au m² avec le loyer mensuel (ex:
    # "CHF 450.-/m2/an" lu comme 450 CHF/mois au lieu du vrai loyer mensuel
    # donné ailleurs dans le texte). Ce cas est géré plus bas, avec garde-fou.
    # "CHF 200.-" : le ".-" (parfois ".–") marque l'absence de centimes et
    # s'intercale entre le nombre et l'unité (ex: "CHF 6'562.-/mois") ; il
    # doit être toléré sans quoi le prix suivi de "/mois" n'est pas détecté.
    cents = r"(?:[.\-–]{1,3})?"
    patterns_monthly = [
        rf"chf\s*([\d'’\s]+){cents}\s*/?\s*(?:mois|month|mo\.?)",
        rf"([\d'’\s]+)\s*chf\s*/?\s*(?:mois|month)",
        rf"loyer\s*(?:mensuel)?\s*chf\s*([\d'’\s]+)",
        r"loyer[^\d]{0,20}([\d'’\s]{3,})",
    ]
    for pat in patterns_monthly:
        m = re.search(pat, t, re.I)
        if m:
            val = _extract_number(m.group(1))
            if val and 300 <= val <= 100000:
                return val

    # --- Montant seul avec CHF (pas de /m²) ---
    # Éviter les prix/m²/an qui ont "m2" ou "m²" dans les 30 chars suivants
    m = re.search(r"chf\s*([\d'’\s]{3,})", t)
    if m:
        # Vérifier que ce n'est pas un prix/m²
        context_after = t[m.end():m.end()+30]
        if not re.search(r"m\s*[²2²]", context_after):
            val = _extract_number(m.group(1))
            if val and 300 <= val <= 100000:
                return val

    return None

def parse_price_m2_month(text: str | None) -> float | None:
    """Extrait CHF/m²/mois depuis le texte (fréquent pour les arcades/dépôts,
    distinct de CHF/m²/an — voir compute_monthly_rent)."""
    if not text:
        return None
    t = normalize(text)
    cents = r"(?:[.\-–]{1,3})?"
    patterns = [
        rf"chf\s*([\d'’\s]+){cents}\s*/?\s*m\s*[²2²]\s*/?\s*(?:mois|month|mo\.?)",
        rf"([\d'’\s]+)\s*chf\s*/?\s*m\s*[²2²]\s*/?\s*(?:mois|month)",
        rf"([\d'’\s]+)\s*/?\s*m\s*[²2²]\s*/?\s*(?:mois|month)",
    ]
    for pat in patterns:
        m = re.search(pat, t)
        if m:
            val = _extract_number(m.group(1))
            if val and 5 <= val <= 500:
                return float(val)
    return None

def parse_price_m2_year(text: str | None) -> float | None:
    """Extrait CHF/m²/an depuis le texte."""
    if not text:
        return None
    t = normalize(text)
    cents = r"(?:[.\-–]{1,3})?"
    patterns = [
        rf"chf\s*([\d'’\s]+){cents}\s*/?\s*m\s*[²2²]\s*/?\s*(?:an|year|yr)",
        rf"([\d'’\s]+)\s*chf\s*/?\s*m\s*[²2²]\s*/?\s*(?:an|year)",
        rf"([\d'’\s]+)\s*/?\s*m\s*[²2²]\s*/?\s*(?:an|year|yr)",
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
    cents = r"(?:[.\-–]{1,3})?"
    m = re.search(rf"chf\s*([\d'’\s]+){cents}\s*/?\s*(?:an|year|yr)(?!\s*/?\s*m)", t)
    if m:
        val = _extract_number(m.group(1))
        if val and 1000 <= val <= 2000000:
            return val
    return None

def compute_monthly_rent(text: str | None, surface_m2: float | None = None) -> int | None:
    """
    Retourne le loyer mensuel en CHF, en normalisant depuis n'importe quelle unité.
    Priorité: CHF/mois > CHF/m²/mois * surface > CHF/an /12 > CHF/m²/an * surface /12
    """
    if not text:
        return None

    # 1. CHF/mois direct
    monthly = parse_price_chf_month(text)
    if monthly:
        return monthly

    # 2. CHF/m²/mois * surface (courant pour arcades/dépôts)
    m2_month = parse_price_m2_month(text)
    if m2_month and surface_m2:
        return int(m2_month * surface_m2)

    # 3. CHF/an → /12
    yearly = parse_price_year(text)
    if yearly:
        return yearly // 12

    # 4. CHF/m²/an * surface / 12
    m2_year = parse_price_m2_year(text)
    if m2_year and surface_m2:
        return int((m2_year * surface_m2) / 12)

    return None

def parse_surface_m2(text: str | None) -> float | None:
    if not text:
        return None
    t = normalize(text).replace(",", ".")
    # Le séparateur de milliers ' / ’ peut apparaître dans les grandes
    # surfaces (ex: "1'280 m2") ; sans le tolérer dans la capture, seule
    # la partie après l'apostrophe était lue (280 au lieu de 1280).
    patterns = [
        r"(\d[\d'’]{1,4}(?:\.\d+)?)\s*m\s*[²2²]",
        r"surface[^\d]{0,20}(\d[\d'’]{1,4}(?:\.\d+)?)",
        r"(\d[\d'’]{1,4}(?:\.\d+)?)\s*m2",
    ]
    for pat in patterns:
        m = re.search(pat, t)
        if m:
            raw = m.group(1).replace("'", "").replace("’", "")
            try:
                val = float(raw)
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
    m = re.search(r"\b(120[5-8])\b", t)
    if m:
        return NPA_TO_DISTRICT.get(m.group(1))
    return None

def extract_possible_changing_room(text: str | None, keywords: list[str]) -> bool:
    t = normalize(text)
    return any(normalize(word) in t for word in keywords)
