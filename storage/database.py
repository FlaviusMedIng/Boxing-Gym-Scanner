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
        # price_history : une ligne par prix observe pour une annonce (la
        # premiere lors de sa decouverte, puis une nouvelle a chaque fois que
        # price_chf change reellement). Table separee plutot qu'une colonne
        # JSON sur `listings` pour pouvoir trier/filtrer par date simplement
        # et parce que `listings` reste un cache "etat courant" regenerable
        # (voir _migrate_if_schema_drifted) alors que l'historique de prix ne
        # doit jamais etre perdu meme si `listings` est un jour reconstruite.
        # `id AUTOINCREMENT` (pas juste `recorded_at`) sert de tie-breaker
        # fiable pour ordonner "premier"/"dernier" prix -- recorded_at n'a
        # qu'une precision a la seconde (CURRENT_TIMESTAMP), donc deux lignes
        # inserees dans la meme seconde (arrive facilement en test, voire en
        # prod si un run traite plusieurs changements tres vite) auraient un
        # ordre indetermine avec ROW_NUMBER() OVER (ORDER BY recorded_at) seul
        # -- bug reel trouve en testant price_history_summary() avant de
        # livrer cette fonctionnalite.
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id  TEXT NOT NULL,
                price_chf   INTEGER,
                recorded_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_price_history_listing_id "
            "ON price_history(listing_id)"
        )
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

    def _record_price(self, listing_id: str, price_chf) -> None:
        self.conn.execute(
            "INSERT INTO price_history (listing_id, price_chf) VALUES (?, ?)",
            (listing_id, price_chf),
        )

    def upsert_listing(self, listing: dict) -> str:
        content_hash = self._content_hash(listing)
        row = self.conn.execute(
            "SELECT id, content_hash, status, price_chf FROM listings WHERE id = ?",
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
            # Premiere observation de prix pour cette annonce -- point de
            # depart de l'historique, meme si price_chf est None (une valeur
            # non publiee au depart peut apparaitre plus tard).
            self._record_price(listing["id"], listing.get("price_chf"))
            self.conn.commit()
            return "new"

        if row["content_hash"] != content_hash or row["status"] != "active":
            # N'ajouter une ligne d'historique que si le prix a REELLEMENT
            # change (pas a chaque "changed", qui peut aussi etre declenche
            # par un texte/statut different) -- comparaison directe, price_chf
            # etant un entier ou None des deux cotes.
            if listing.get("price_chf") != row["price_chf"]:
                self._record_price(listing["id"], listing.get("price_chf"))

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

    def price_history_summary(self) -> dict[str, dict]:
        """Per listing_id: {first_price_chf, latest_price_chf, price_dropped}.

        One query for all listings (used by site_generator/dashboard) rather
        than one query per listing -- this table can grow to thousands of
        rows over time and N+1 queries would get slow on every scan.
        """
        rows = self.conn.execute('''
            SELECT listing_id, price_chf, recorded_at,
                   ROW_NUMBER() OVER (PARTITION BY listing_id ORDER BY id ASC) AS rn_asc,
                   ROW_NUMBER() OVER (PARTITION BY listing_id ORDER BY id DESC) AS rn_desc
            FROM price_history
        ''').fetchall()
        summary: dict[str, dict] = {}
        for r in rows:
            entry = summary.setdefault(r["listing_id"], {"first_price_chf": None, "latest_price_chf": None})
            if r["rn_asc"] == 1:
                entry["first_price_chf"] = r["price_chf"]
            if r["rn_desc"] == 1:
                entry["latest_price_chf"] = r["price_chf"]
        for entry in summary.values():
            first, latest = entry["first_price_chf"], entry["latest_price_chf"]
            entry["price_dropped"] = bool(
                first is not None and latest is not None and latest < first
            )
        return summary

    def price_history_for(self, listing_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT price_chf, recorded_at FROM price_history "
            "WHERE listing_id = ? ORDER BY id ASC",
            (listing_id,),
        ).fetchall()
        return [dict(r) for r in rows]

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
