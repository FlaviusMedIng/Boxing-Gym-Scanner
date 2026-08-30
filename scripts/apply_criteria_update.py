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
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from utils.parser import DISTRICTS as KNOWN_DISTRICTS
from utils.parser import PROPERTY_TYPES as KNOWN_PROPERTY_TYPES

CONFIG_PATH = Path("config.yaml")
SCANNER_WORKFLOW_PATH = Path(".github/workflows/scanner.yml")


def geneva_hour_to_utc(hour: int) -> int:
    """Convertit une heure locale de Genève (0-23) en heure UTC, pour la
    date du jour — donc correcte selon que l'heure d'été (CEST, UTC+2) ou
    d'hiver (CET, UTC+1) est en vigueur au moment de l'appel. Le cron GitHub
    Actions n'a pas de notion de fuseau horaire : la valeur UTC calculée ici
    est figée jusqu'au prochain changement d'heure (fin mars / fin
    octobre), où elle dérivera d'1h tant que personne ne la réajuste (via ce
    même formulaire, ou en relançant [criteria-update] avec la même heure)."""
    geneva = ZoneInfo("Europe/Zurich")
    local_dt = datetime.now(geneva).replace(hour=hour, minute=0, second=0, microsecond=0)
    return local_dt.astimezone(ZoneInfo("UTC")).hour


def parse_issue_body(body: str) -> dict:
    fields = {}
    for line in body.splitlines():
        # "types" peut être vide (tous les types acceptés) : (.*) plutôt que
        # (.+?) pour capturer une chaîne vide sans que la ligne soit ignorée.
        m = re.match(
            r"^\s*(surface_min|loyer_max|quartiers|types|vestiaires_requis|heure_scan)\s*:\s*(.*?)\s*$",
            line,
        )
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

    scan_hour = None
    if fields.get("heure_scan", "").strip():
        scan_hour = int(fields["heure_scan"])
        if not (0 <= scan_hour <= 23):
            raise ValueError(f"Heure de scan hors limites: {scan_hour}")

    return {
        "min_surface_m2": surface,
        "max_rent_chf_month": rent,
        "allowed_districts": districts,
        "allowed_property_types": property_types,
        "require_possible_changing_rooms": changing_room,
        "scan_hour_geneva": scan_hour,
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

    if values.get("scan_hour_geneva") is not None:
        text = re.sub(
            r"(?m)^(\s*scan_hour_geneva:\s*)\d+",
            lambda m: f"{m.group(1)}{values['scan_hour_geneva']}",
            text,
            count=1,
        )
    return text


def apply_to_scanner_workflow_text(text: str, scan_hour_geneva: int) -> str:
    utc_hour = geneva_hour_to_utc(scan_hour_geneva)
    return re.sub(
        r"(?m)^(\s*- cron:\s*)'0 \d{1,2} \* \* \*'",
        lambda m: f"{m.group(1)}'0 {utc_hour} * * *'",
        text,
        count=1,
    )


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
    if values.get("scan_hour_geneva") is not None:
        assert parsed.get("runtime", {}).get("scan_hour_geneva") == values["scan_hour_geneva"]

    changed_files = []
    if updated != original:
        CONFIG_PATH.write_text(updated, encoding="utf-8")
        changed_files.append(str(CONFIG_PATH))

    if values.get("scan_hour_geneva") is not None:
        original_workflow = SCANNER_WORKFLOW_PATH.read_text(encoding="utf-8")
        updated_workflow = apply_to_scanner_workflow_text(original_workflow, values["scan_hour_geneva"])
        # Filet de sécurité : le fichier doit rester un YAML valide.
        yaml.safe_load(updated_workflow)
        if updated_workflow != original_workflow:
            SCANNER_WORKFLOW_PATH.write_text(updated_workflow, encoding="utf-8")
            changed_files.append(str(SCANNER_WORKFLOW_PATH))

    if not changed_files:
        print("Aucun changement (critères déjà à jour).")
        return 0

    print(f"Fichiers mis à jour ({', '.join(changed_files)}): {values}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
