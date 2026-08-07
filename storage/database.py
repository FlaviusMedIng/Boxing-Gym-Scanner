from __future__ import annotations
import hashlib
import sqlite3
from pathlib import Path

class Database:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    EXPECTED_COLUMNS = {
        "id", "site", "title", "url", "price_chf", "surface_m2", "district",
        "location_hint", "text_blob", "possible_changing_room", "property_type",
        "score", "matches", "status", "first_seen_at", "last_seen_at",
        "last_changed_at", "content_hash",
    }

    def init_db(self) -> None:
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS listings (
                id                    TEXT PRIMARY KEY,
                site                  TEXT NOT NULL,
                title                 TEXT,
                url                   TEXT NOT NULL,
                price_chf             INTEGER,
                surface_m2            REAL,
                district              TEXT,
                location_hint         TEXT,
                text_blob             TEXT,
                possible_changing_room INTEGER DEFAULT 0,
                property_type         TEXT,
                score                 INTEGER DEFAULT 0,
                matches               INTEGER DEFAULT 0,
                status                TEXT DEFAULT 'active',
                first_seen_at         TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen_at          TEXT DEFAULT CURRENT_TIMESTAMP,
                last_changed_at       TEXT DEFAULT CURRENT_TIMESTAMP,
                content_hash          TEXT
            )
        ''')
        self._migrate_if_schema_drifted()
        self.conn.commit()

    def _migrate_if_schema_drifted(self) -> None:
        # Une base créée par une version antérieure du scanner peut avoir un
        # schéma différent (ex: "price_chf_month" au lieu de "price_chf").
        # "CREATE TABLE IF NOT EXISTS" ne migre rien dans ce cas ; comme il
        # s'agit d'un simple cache régénérable (pas de données saisies par
        # l'utilisateur), on repart d'une table vide plutôt que de planter
        # sur chaque upsert.
        existing = {row["name"] for row in self.conn.execute("PRAGMA table_info(listings)")}
        if existing and existing != self.EXPECTED_COLUMNS:
            self.conn.execute("ALTER TABLE listings RENAME TO listings_old_schema")
            self.conn.execute('''
                CREATE TABLE listings (
                    id                    TEXT PRIMARY KEY,
                    site                  TEXT NOT NULL,
                    title                 TEXT,
                    url                   TEXT NOT NULL,
                    price_chf             INTEGER,
                    surface_m2            REAL,
                    district              TEXT,
                    location_hint         TEXT,
                    text_blob             TEXT,
                    possible_changing_room INTEGER DEFAULT 0,
                    property_type         TEXT,
                    score                 INTEGER DEFAULT 0,
                    matches               INTEGER DEFAULT 0,
                    status                TEXT DEFAULT 'active',
                    first_seen_at         TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_seen_at          TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_changed_at       TEXT DEFAULT CURRENT_TIMESTAMP,
                    content_hash          TEXT
                )
            ''')

    @staticmethod
    def _content_hash(listing: dict) -> str:
        raw = "|".join(str(listing.get(k, "")) for k in [
            "title", "price_chf", "surface_m2", "district",
            "possible_changing_room", "property_type", "score", "matches"
        ])
        return hashlib.sha1(raw.encode()).hexdigest()

    def upsert_listing(self, listing: dict) -> str:
        content_hash = self._content_hash(listing)
        row = self.conn.execute(
            "SELECT id, content_hash, status FROM listings WHERE id = ?",
            (listing["id"],)
        ).fetchone()

        if row is None:
            self.conn.execute('''
                INSERT INTO listings (
                    id, site, title, url, price_chf, surface_m2,
                    district, location_hint, text_blob,
                    possible_changing_room, property_type, score, matches, status, content_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)
            ''', (
                listing["id"], listing["site"], listing.get("title"), listing["url"],
                listing.get("price_chf"), listing.get("surface_m2"),
                listing.get("district"), listing.get("location_hint"),
                listing.get("text_blob"),
                int(bool(listing.get("possible_changing_room"))),
                listing.get("property_type"),
                listing.get("score", 0), int(bool(listing.get("matches"))),
                content_hash
            ))
            self.conn.commit()
            return "new"

        if row["content_hash"] != content_hash or row["status"] != "active":
            self.conn.execute('''
                UPDATE listings SET
                    title=?, url=?, price_chf=?, surface_m2=?,
                    district=?, location_hint=?, text_blob=?,
                    possible_changing_room=?, property_type=?, score=?, matches=?,
                    status='active', content_hash=?,
                    last_seen_at=CURRENT_TIMESTAMP,
                    last_changed_at=CURRENT_TIMESTAMP
                WHERE id=?
            ''', (
                listing.get("title"), listing["url"],
                listing.get("price_chf"), listing.get("surface_m2"),
                listing.get("district"), listing.get("location_hint"),
                listing.get("text_blob"),
                int(bool(listing.get("possible_changing_room"))),
                listing.get("property_type"),
                listing.get("score", 0), int(bool(listing.get("matches"))),
                content_hash, listing["id"]
            ))
            self.conn.commit()
            return "changed"

        self.conn.execute(
            "UPDATE listings SET last_seen_at=CURRENT_TIMESTAMP, status='active' WHERE id=?",
            (listing["id"],)
        )
        self.conn.commit()
        return "unchanged"

    def mark_missing_as_removed(self, current_ids: set[str]) -> None:
        if current_ids:
            placeholders = ",".join("?" * len(current_ids))
            self.conn.execute(
                f"UPDATE listings SET status='removed', last_changed_at=CURRENT_TIMESTAMP "
                f"WHERE id NOT IN ({placeholders}) AND status='active'",
                tuple(current_ids)
            )
        else:
            self.conn.execute(
                "UPDATE listings SET status='removed', last_changed_at=CURRENT_TIMESTAMP WHERE status='active'"
            )
        self.conn.commit()

    def dataframe(self):
        import pandas as pd
        return pd.read_sql_query(
            "SELECT * FROM listings ORDER BY score DESC, last_seen_at DESC",
            self.conn
        )
