import sqlite3
from datetime import datetime


DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS publications (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    source_id TEXT,

    title TEXT,

    url TEXT UNIQUE,

    content_hash TEXT,

    domain TEXT,

    topic TEXT,

    action_type TEXT,

    impact_score INTEGER,

    first_seen TEXT,

    last_seen TEXT
);

CREATE TABLE IF NOT EXISTS runs (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    started_at TEXT,

    finished_at TEXT,

    publications_found INTEGER
);
"""


class Database:

    def __init__(self, path: str):

        self.conn = sqlite3.connect(path)

        self.conn.executescript(DB_SCHEMA)

        self.conn.commit()

    def get_hash(self, url: str):

        cursor = self.conn.cursor()

        cursor.execute(
            """
            SELECT content_hash
            FROM publications
            WHERE url = ?
            """,
            (url,)
        )

        row = cursor.fetchone()

        if row:
            return row[0]

        return None

    def save_publication(self, publication: dict):

        now = datetime.utcnow().isoformat()

        cursor = self.conn.cursor()

        cursor.execute(
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
                first_seen,
                last_seen

            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(url)
            DO UPDATE SET

                content_hash = excluded.content_hash,
                domain = excluded.domain,
                topic = excluded.topic,
                action_type = excluded.action_type,
                impact_score = excluded.impact_score,
                last_seen = excluded.last_seen
            """,
            (
                publication["source_id"],
                publication["title"],
                publication["url"],
                publication["hash_value"],
                publication.get("domain"),
                publication.get("topic"),
                publication.get("action_type"),
                publication.get("impact_score", 0),
                now,
                now,
            )
        )

        self.conn.commit()

    def start_run(self):

        cursor = self.conn.cursor()

        cursor.execute(
            """
            INSERT INTO runs (
                started_at,
                finished_at,
                publications_found
            )
            VALUES (?, ?, ?)
            """,
            (
                datetime.utcnow().isoformat(),
                None,
                0
            )
        )

        self.conn.commit()

        return cursor.lastrowid

    def finish_run(
        self,
        run_id,
        publications_found
    ):

        cursor = self.conn.cursor()

        cursor.execute(
            """
            UPDATE runs
            SET
                finished_at = ?,
                publications_found = ?
            WHERE id = ?
            """,
            (
                datetime.utcnow().isoformat(),
                publications_found,
                run_id
            )
        )

        self.conn.commit()

    def close(self):

        self.conn.close()