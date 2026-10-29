import sqlite3
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from regwatch.date_filter import to_utc
from regwatch.models import Publication

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS publications (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    source_id TEXT NOT NULL,

    title TEXT,

    url TEXT NOT NULL UNIQUE,

    content_hash TEXT,

    domain TEXT,

    topic TEXT,

    action_type TEXT,

    impact_score INTEGER DEFAULT 0,

    published_date TEXT,

    first_seen TEXT,

    last_seen TEXT
);

CREATE TABLE IF NOT EXISTS runs (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    started_at TEXT,

    finished_at TEXT,

    publications_found INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_publications_last_seen
    ON publications(last_seen);

CREATE INDEX IF NOT EXISTS idx_publications_domain
    ON publications(domain, topic);
"""

# Columns added after the first release. ``CREATE TABLE IF NOT EXISTS`` does
# not alter existing databases, so they are added explicitly when missing.
MIGRATIONS = {
    "published_date": "TEXT",
    "impact_score": "INTEGER DEFAULT 0",
}

PUBLICATION_COLUMNS = (
    "id, source_id, title, url, content_hash, domain, topic, "
    "action_type, impact_score, published_date, first_seen, last_seen"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(DB_SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        existing = {
            row["name"]
            for row in self.conn.execute("PRAGMA table_info(publications)")
        }

        for column, definition in MIGRATIONS.items():
            if column not in existing:
                self.conn.execute(
                    f"ALTER TABLE publications ADD COLUMN {column} {definition}"
                )

    def get_hash(self, url: str) -> Optional[str]:
        row = self.conn.execute(
            "SELECT content_hash FROM publications WHERE url = ?",
            (url,),
        ).fetchone()

        return row["content_hash"] if row else None

    def save_publication(self, publication: Publication) -> None:
        now = _now()
        published = (
            to_utc(publication.published_date).isoformat()
            if publication.published_date
            else None
        )

        self.conn.execute(
            """
            INSERT INTO publications (
                source_id,
                title,
                url,
                content_hash,
                domain,
                topic,
                action_type,
                impact_score,
                published_date,
                first_seen,
                last_seen
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(url)
            DO UPDATE SET
                source_id = excluded.source_id,
                title = excluded.title,
                content_hash = excluded.content_hash,
                domain = excluded.domain,
                topic = excluded.topic,
                action_type = excluded.action_type,
                impact_score = excluded.impact_score,
                published_date = COALESCE(
                    excluded.published_date,
                    publications.published_date
                ),
                last_seen = excluded.last_seen
            """,
            (
                publication.source_id,
                publication.title,
                publication.url,
                publication.hash_value,
                publication.domain,
                publication.topic,
                publication.action_type,
                publication.impact_score,
                published,
                now,
                now,
            ),
        )

        self.conn.commit()

    def start_run(self) -> int:
        cursor = self.conn.execute(
            """
            INSERT INTO runs (started_at, finished_at, publications_found)
            VALUES (?, ?, ?)
            """,
            (_now(), None, 0),
        )

        self.conn.commit()

        return int(cursor.lastrowid)

    def finish_run(self, run_id: int, publications_found: int) -> None:
        self.conn.execute(
            """
            UPDATE runs
            SET finished_at = ?, publications_found = ?
            WHERE id = ?
            """,
            (_now(), publications_found, run_id),
        )

        self.conn.commit()

    def recent_publications(self, lookback_days: int) -> List[sqlite3.Row]:
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=lookback_days)
        ).isoformat()

        return list(
            self.conn.execute(
                f"""
                SELECT {PUBLICATION_COLUMNS}
                FROM publications
                WHERE last_seen >= ?
                ORDER BY impact_score DESC, last_seen DESC
                """,
                (cutoff,),
            )
        )

    def count_publications(self) -> int:
        row = self.conn.execute(
            "SELECT COUNT(*) AS total FROM publications"
        ).fetchone()

        return int(row["total"]) if row else 0

    def mark_seen(self, url: str) -> None:
        self.conn.execute(
            "UPDATE publications SET last_seen = ? WHERE url = ?",
            (_now(), url),
        )

        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
