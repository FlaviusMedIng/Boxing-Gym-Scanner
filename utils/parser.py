from __future__ import annotations

import re
import unicodedata


DISTRICTS = [
    "Champel",
    "Eaux-Vives",
    "Rive",
    "Rives",
    "Plainpalais",
    "Jonction",
    "Carouge",
    "Acacias",
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


def parse_price_chf_month(text: str | None):
    if not text:
        return None
    t = normalize(text)
    patterns = [
        r"(\d[\d'\s]{2,})\s*chf\s*/?\s*mois",
        r"(\d[\d'\s]{2,})\s*fr\.?\s*/?\s*mois",
        r"loyer[^\d]{0,20}(\d[\d'\s]{2,})",
        r"(\d[\d'\s]{2,})\s*chf",
    ]
    for pat in patterns:
        m = re.search(pat, t, flags=re.I)
        if m:
            raw = re.sub(r"[^\d]", "", m.group(1))
            if raw:
                value = int(raw)
                if 200 <= value <= 100000:
                    return value
    return None


def parse_surface_m2(text: str | None):
    if not text:
        return None
    t = normalize(text).replace(",", ".")
    patterns = [
        r"(\d{2,4}(?:\.\d+)?)\s*m2",
        r"(\d{2,4}(?:\.\d+)?)\s*m²",
        r"surface[^\d]{0,20}(\d{2,4}(?:\.\d+)?)",
    ]
    for pat in patterns:
        m = re.search(pat, t, flags=re.I)
        if m:
            try:
                value = float(m.group(1))
            except ValueError:
                continue
            if 20 <= value <= 10000:
                return value
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
