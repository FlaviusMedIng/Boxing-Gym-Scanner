from __future__ import annotations

from pathlib import Path


def export_all(processed: list[dict], db, config: dict) -> None:
    Path("data").mkdir(exist_ok=True)

    df_db = db.dataframe()
    export_cols = [
        "site", "title", "price_chf_month", "surface_m2", "district", "location_text",
        "possible_changing_room", "score", "matches", "status", "url", "first_seen_at",
        "last_seen_at", "last_changed_at"
    ]
    df_db = df_db[[c for c in export_cols if c in df_db.columns]]

    df_db.to_excel(config["output"]["excel_path"], index=False)
    df_db.to_csv(config["output"]["csv_path"], index=False)
