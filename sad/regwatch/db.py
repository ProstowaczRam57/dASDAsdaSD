import sqlite3
import zlib
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

    previous_hash TEXT,

    body BLOB,

    previous_body BLOB,

    change_type TEXT,

    change_summary TEXT,

    summary_generated_at TEXT,

    domain TEXT,

    topic TEXT,

    action_type TEXT,

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
    "body": "BLOB",
    "previous_body": "BLOB",
    "previous_hash": "TEXT",
    "change_type": "TEXT",
    "change_summary": "TEXT",
    "summary_generated_at": "TEXT",
}

PUBLICATION_LIST_COLUMNS = (
    "id, source_id, title, url, content_hash, previous_hash, "
    "change_type, change_summary, summary_generated_at, domain, topic, "
    "action_type, published_date, first_seen, last_seen"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pack(text: Optional[str]) -> Optional[bytes]:
    if text is None:
        return None

    return zlib.compress(text.encode("utf-8"), level=9)


def _unpack(blob: Optional[bytes]) -> str:
    if not blob:
        return ""

    return zlib.decompress(blob).decode("utf-8")


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

        # Scores were removed from the product; drop the old column when the
        # SQLite version supports it (3.35+).
        if "impact_score" in existing:
            try:
                self.conn.execute(
                    "ALTER TABLE publications DROP COLUMN impact_score"
                )
            except sqlite3.OperationalError:
                pass

    def get_hash(self, url: str) -> Optional[str]:
        state = self.get_state(url)

        return state["content_hash"] if state else None

    def get_state(self, url: str) -> Optional[dict]:
        row = self.conn.execute(
            """
            SELECT content_hash, title, body
            FROM publications
            WHERE url = ?
            """,
            (url,),
        ).fetchone()

        if row is None:
            return None

        return {
            "content_hash": row["content_hash"],
            "title": row["title"],
            "body": _unpack(row["body"]),
        }

    def get_publication(self, url: str) -> Optional[dict]:
        row = self.conn.execute(
            f"""
            SELECT {PUBLICATION_LIST_COLUMNS}, body, previous_body
            FROM publications
            WHERE url = ?
            """,
            (url,),
        ).fetchone()

        if row is None:
            return None

        publication = dict(row)
        publication["body"] = _unpack(row["body"])
        publication["previous_body"] = _unpack(row["previous_body"])

        return publication

    def save_publication(self, publication: Publication) -> None:
        now = _now()
        published = (
            to_utc(publication.published_date).isoformat()
            if publication.published_date
            else None
        )
        summarised = (
            to_utc(publication.summary_generated_at).isoformat()
            if publication.summary_generated_at
            else None
        )

        self.conn.execute(
            """
            INSERT INTO publications (
                source_id,
                title,
                url,
                content_hash,
                previous_hash,
                body,
                previous_body,
                change_type,
                change_summary,
                summary_generated_at,
                domain,
                topic,
                action_type,
                published_date,
                first_seen,
                last_seen
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(url)
            DO UPDATE SET
                source_id = excluded.source_id,
                title = excluded.title,
                content_hash = excluded.content_hash,
                previous_hash = excluded.previous_hash,
                body = excluded.body,
                previous_body = excluded.previous_body,
                change_type = excluded.change_type,
                change_summary = excluded.change_summary,
                summary_generated_at = excluded.summary_generated_at,
                domain = excluded.domain,
                topic = excluded.topic,
                action_type = excluded.action_type,
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
                publication.content_hash,
                publication.previous_hash,
                _pack(publication.body),
                _pack(publication.previous_body),
                publication.change_type,
                publication.change_summary,
                summarised,
                publication.domain,
                publication.topic,
                publication.action_type,
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
                SELECT {PUBLICATION_LIST_COLUMNS}
                FROM publications
                WHERE last_seen >= ?
                ORDER BY last_seen DESC
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
