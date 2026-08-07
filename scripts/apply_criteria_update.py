"""Applique à config.yaml les critères demandés via une issue GitHub créée
par docs/criteria.html + worker/criteria-worker.js (voir README.md, section
"Modifier les critères depuis le site").

Invoqué par .github/workflows/apply-criteria.yml avec le corps de l'issue
dans la variable d'environnement ISSUE_BODY. Édite config.yaml par
substitution de texte ciblée (pas un dump YAML complet) pour préserver les
commentaires existants dans le fichier.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import yaml

from utils.parser import DISTRICTS as KNOWN_DISTRICTS
from utils.parser import PROPERTY_TYPES as KNOWN_PROPERTY_TYPES

CONFIG_PATH = Path("config.yaml")


def parse_issue_body(body: str) -> dict:
    fields = {}
    for line in body.splitlines():
        # "types" peut être vide (tous les types acceptés) : (.*) plutôt que
        # (.+?) pour capturer une chaîne vide sans que la ligne soit ignorée.
        m = re.match(r"^\s*(surface_min|loyer_max|quartiers|types|vestiaires_requis)\s*:\s*(.*?)\s*$", line)
        if m:
            fields[m.group(1)] = m.group(2)
    return fields


def validate(fields: dict) -> dict:
    if "surface_min" not in fields or "loyer_max" not in fields or "quartiers" not in fields:
        raise ValueError(f"Champs manquants dans l'issue: {fields}")

    surface = int(fields["surface_min"])
    if not (1 <= surface <= 5000):
        raise ValueError(f"Surface hors limites: {surface}")

    rent = int(fields["loyer_max"])
    if not (1 <= rent <= 100000):
        raise ValueError(f"Loyer hors limites: {rent}")

    districts = [d.strip() for d in fields["quartiers"].split(",") if d.strip()]
    districts = [d for d in districts if d in KNOWN_DISTRICTS]
    if not districts:
        raise ValueError("Aucun quartier valide dans la demande")

    property_types = [t.strip() for t in fields.get("types", "").split(",") if t.strip()]
    property_types = [t for t in property_types if t in KNOWN_PROPERTY_TYPES]
    if not property_types:
        raise ValueError("Aucun type de bien valide dans la demande")

    changing_room = fields.get("vestiaires_requis", "oui").strip().lower() == "oui"

    return {
        "min_surface_m2": surface,
        "max_rent_chf_month": rent,
        "allowed_districts": districts,
        "allowed_property_types": property_types,
        "require_possible_changing_rooms": changing_room,
    }


def apply_to_config_text(text: str, values: dict) -> str:
    text = re.sub(
        r"(?m)^(\s*min_surface_m2:\s*)\d+",
        lambda m: f"{m.group(1)}{values['min_surface_m2']}",
        text,
        count=1,
    )
    text = re.sub(
        r"(?m)^(\s*max_rent_chf_month:\s*)\d+",
        lambda m: f"{m.group(1)}{values['max_rent_chf_month']}",
        text,
        count=1,
    )
    text = re.sub(
        r"(?m)^(\s*require_possible_changing_rooms:\s*)(true|false)",
        lambda m: f"{m.group(1)}{'true' if values['require_possible_changing_rooms'] else 'false'}",
        text,
        count=1,
    )

    new_district_lines = "".join(f"    - {d}\n" for d in values["allowed_districts"])
    text = re.sub(
        r"(  allowed_districts:\n)(?:    - .*\n)+",
        lambda m: m.group(1) + new_district_lines,
        text,
        count=1,
    )

    new_type_lines = "".join(f"    - {t}\n" for t in values["allowed_property_types"])
    text = re.sub(
        r"(  allowed_property_types:\n)(?:    - .*\n)+",
        lambda m: m.group(1) + new_type_lines,
        text,
        count=1,
    )
    return text


def main() -> int:
    issue_body = os.environ.get("ISSUE_BODY", "")
    fields = parse_issue_body(issue_body)
    try:
        values = validate(fields)
    except ValueError as exc:
        print(f"Demande rejetée: {exc}", file=sys.stderr)
        return 1

    original = CONFIG_PATH.read_text(encoding="utf-8")
    updated = apply_to_config_text(original, values)

    # Filet de sécurité : le fichier doit rester un YAML valide et refléter
    # les valeurs attendues avant d'être écrit.
    parsed = yaml.safe_load(updated)
    criteria = parsed.get("criteria", {})
    assert criteria.get("min_surface_m2") == values["min_surface_m2"]
    assert criteria.get("max_rent_chf_month") == values["max_rent_chf_month"]
    assert criteria.get("allowed_districts") == values["allowed_districts"]
    assert criteria.get("allowed_property_types") == values["allowed_property_types"]
    assert criteria.get("require_possible_changing_rooms") == values["require_possible_changing_rooms"]

    if updated == original:
        print("Aucun changement (critères déjà à jour).")
        return 0

    CONFIG_PATH.write_text(updated, encoding="utf-8")
    print(f"config.yaml mis à jour: {values}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
