from __future__ import annotations
from pathlib import Path

def export_all(processed: list[dict], db, config: dict) -> None:
    Path("data").mkdir(exist_ok=True)
    df = db.dataframe()

    export_cols = [
        "site", "title", "price_chf", "surface_m2", "district",
        "location_hint", "possible_changing_room", "score", "matches",
        "status", "url", "first_seen_at", "last_seen_at", "last_changed_at"
    ]
    df = df[[c for c in export_cols if c in df.columns]]

    df.to_excel(config["output"]["excel_path"], index=False)
    df.to_csv(config["output"]["csv_path"], index=False)
