from __future__ import annotations
from pathlib import Path
from filters.gym_filter import matches_criteria
from notifier.email_notifier import send_email
from notifier.telegram_notifier import send_telegram
from scoring.gym_score import compute_score
from scrapers import build_scrapers
from storage.database import Database
from storage.excel_export import export_all
from utils.config import load_config
from utils.logger import get_logger
import hashlib

def make_id(listing: dict) -> str:
    """Génère un ID stable basé sur l'URL."""
    url = listing.get("url") or ""
    return hashlib.md5(url.encode()).hexdigest()

def format_listing_message(listing: dict) -> str:
    return (
        f"[{listing['site']}] {listing['title']}\n"
        f"Loyer: {listing.get('price_chf') or 'N/A'} CHF/mois\n"
        f"Surface: {listing.get('surface_m2') or 'N/A'} m²\n"
        f"Score: {listing.get('score', 0)}\n"
        f"Lien: {listing['url']}"
    )

def main() -> int:
    config = load_config("config.yaml")
    logger = get_logger(config["output"]["log_path"])
    Path("data").mkdir(exist_ok=True)

    db = Database(config["output"]["sqlite_path"])
    db.init_db()

    scrapers = build_scrapers(config, logger)
    all_raw: list[dict] = []
    for scraper in scrapers:
        try:
            logger.info("Running scraper: %s", scraper.name)
            items = scraper.scrape()
            logger.info("%s returned %s listings", scraper.name, len(items))
            all_raw.extend(items)
        except Exception as exc:
            logger.exception("Scraper %s failed: %s", scraper.name, exc)

    processed: list[dict] = []
    new_listings: list[dict] = []
    changed_listings: list[dict] = []
    seen_ids: set[str] = set()

    for listing in all_raw:
        # Ignorer les listings sans URL
        if not listing.get("url"):
            logger.warning("Listing sans URL ignoré: %s", listing)
            continue

        # Générer l'ID depuis l'URL si absent
        if not listing.get("id"):
            listing["id"] = make_id(listing)

        if listing["id"] in seen_ids:
            continue
        seen_ids.add(listing["id"])

        listing["score"] = compute_score(listing, config)
        listing["matches"] = matches_criteria(listing, config)

        processed.append(listing)

        change_type = db.upsert_listing(listing)
        if listing["matches"]:
            if change_type == "new":
                new_listings.append(listing)
            elif change_type == "changed":
                changed_listings.append(listing)

    db.mark_missing_as_removed(seen_ids)
    export_all(processed, db, config)

    logger.info(
        "Run complete. Total scraped=%s | processed=%s | new=%s | changed=%s",
        len(all_raw), len(processed), len(new_listings), len(changed_listings)
    )

    messages: list[str] = []
    if new_listings:
        messages.append(
            "Nouvelles annonces:\n\n" +
            "\n\n".join(format_listing_message(x) for x in new_listings[:10])
        )
    if changed_listings:
        messages.append(
            "Annonces modifiées:\n\n" +
            "\n\n".join(format_listing_message(x) for x in changed_listings[:10])
        )

    joined_message = "\n\n---\n\n".join(messages).strip()
    if joined_message:
        if config["notifications"].get("telegram_enabled", False):
            send_telegram(joined_message, logger)
        if config["notifications"].get("email_enabled", False):
            send_email(
                subject="Geneva Gym Scanner - nouvelles annonces",
                body=joined_message,
                logger=logger,
            )
    else:
        logger.info("No new or changed matching listings.")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
