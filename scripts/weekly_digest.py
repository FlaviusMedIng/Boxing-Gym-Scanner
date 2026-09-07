from __future__ import annotations

"""Digest hebdomadaire -- complement aux alertes quotidiennes immediates.

Le scan quotidien (main.py) ne notifie que sur de VRAIES nouvelles annonces
(decision du 2026-08-30, voir CLAUDE.md) : un changement de prix seul ne
declenche plus rien, volontairement, pour ne pas spammer. Ce script ne
change pas cette regle -- il lit juste la meme base SQLite (deja a jour,
committee par le scan quotidien) une fois par semaine pour donner une vue
d'ensemble que les notifications immediates ne montrent jamais : le nombre
d'annonces actives qui correspondent aux criteres, celles qui trainent
depuis longtemps (levier de negociation), et celles dont le prix a baisse
depuis leur decouverte. Ne re-scrape rien, ne modifie pas la base.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from notifier.email_notifier import send_email
from notifier.telegram_notifier import send_telegram
from storage.database import Database
from utils.config import load_config
from utils.logger import get_logger

TOP_N = 5
LONGEST_LISTED_N = 5
LONG_LISTED_THRESHOLD_DAYS = 21


def _days_listed(first_seen_at: str | None) -> int | None:
    from datetime import datetime, timezone

    if not first_seen_at:
        return None
    try:
        first_seen = datetime.strptime(first_seen_at, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return max(0, (datetime.now(timezone.utc) - first_seen).days)


def build_digest(db: Database) -> str:
    df = db.dataframe()
    price_summary = db.price_history_summary()

    active_matches = df[(df["status"] == "active") & (df["matches"] == 1)].copy()
    # fillna(-1) : first_seen_at ne devrait jamais etre vide (defaut SQL
    # CURRENT_TIMESTAMP), mais un None non gere ferait planter la comparaison
    # ">=" plus bas sur une colonne object -- filet de securite bon marche.
    active_matches["days_listed"] = active_matches["first_seen_at"].map(_days_listed).fillna(-1)
    active_matches["price_dropped"] = active_matches["id"].map(
        lambda i: bool(price_summary.get(i, {}).get("price_dropped"))
    )
    active_matches["initial_price_chf"] = active_matches["id"].map(
        lambda i: price_summary.get(i, {}).get("first_price_chf")
    )

    lines = [
        "Digest hebdomadaire - Geneva Gym Scanner",
        "",
        f"{len(active_matches)} annonce(s) active(s) correspondant aux criteres actuellement.",
    ]

    if active_matches.empty:
        lines.append("\nRien a montrer cette semaine.")
        return "\n".join(lines)

    top = active_matches.sort_values("score", ascending=False).head(TOP_N)
    lines.append(f"\nTop {len(top)} par score :")
    for _, row in top.iterrows():
        lines.append(
            f"- [{row['site']}] {row['title']} -- {row.get('price_chf') or 'N/A'} CHF/mois, "
            f"{row.get('surface_m2') or 'N/A'} m2, score {row['score']} -- {row['url']}"
        )

    long_listed = active_matches[active_matches["days_listed"] >= LONG_LISTED_THRESHOLD_DAYS]
    long_listed = long_listed.sort_values("days_listed", ascending=False).head(LONGEST_LISTED_N)
    if not long_listed.empty:
        lines.append(
            f"\nEn ligne depuis {LONG_LISTED_THRESHOLD_DAYS}+ jours (levier de negociation possible) :"
        )
        for _, row in long_listed.iterrows():
            lines.append(
                f"- [{row['site']}] {row['title']} -- {int(row['days_listed'])} jours -- {row['url']}"
            )

    dropped = active_matches[active_matches["price_dropped"]]
    if not dropped.empty:
        lines.append("\nPrix en baisse depuis la premiere observation :")
        for _, row in dropped.iterrows():
            lines.append(
                f"- [{row['site']}] {row['title']} -- {row['initial_price_chf']} -> "
                f"{row['price_chf']} CHF/mois -- {row['url']}"
            )

    return "\n".join(lines)


def main() -> int:
    config = load_config("config.yaml")
    logger = get_logger(config["output"]["log_path"])

    db = Database(config["output"]["sqlite_path"])
    db.init_db()

    message = build_digest(db)
    logger.info("Weekly digest built:\n%s", message)

    site_url = (config["output"].get("site_url") or "").rstrip("/")
    footer = f"\n\n---\nVoir toutes les annonces: {site_url}/" if site_url else ""

    if config["notifications"].get("telegram_enabled", False):
        send_telegram((message + footer)[:4000], logger)
    if config["notifications"].get("email_enabled", False):
        send_email(
            subject="Geneva Gym Scanner - digest hebdomadaire",
            body=message + footer,
            logger=logger,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
