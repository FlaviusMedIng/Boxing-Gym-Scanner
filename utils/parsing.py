import re


def parse_price(text):

    if not text:
        return None

    text = text.replace("’", "").replace("'", "")

    m = re.search(r"CHF\s*([0-9]+)", text)

    if m:
        return float(m.group(1))

    return None


def parse_surface(text):

    if not text:
        return None

    m = re.search(r"([0-9]+)\s*m", text)

    if m:
        return float(m.group(1))

    return None
