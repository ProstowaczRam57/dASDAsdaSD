import sqlite3
from datetime import datetime, timezone

import pytest
from regwatch.db import Database
from regwatch.models import Publication


@pytest.fixture()
def db(tmp_path):
    database = Database(str(tmp_path / "state.db"))
    yield database
    database.close()


def _publication(**overrides):
    values = {
        "source_id": "ca_carb_rulemaking",
        "source_name": "CARB",
        "title": "PFAS rule",
        "url": "https://example.com/rule/1",
        "content": "Final rule text",
        "hash_value": "hash-1",
        "published_date": datetime(2026, 10, 20, tzinfo=timezone.utc),
        "domain": "environment",
        "topic": "pfas",
        "action_type": "final_rule",
        "impact_score": 10,
    }
    values.update(overrides)
    return Publication(**values)


def test_save_and_get_hash(db):
    db.save_publication(_publication())

    assert db.get_hash("https://example.com/rule/1") == "hash-1"
    assert db.get_hash("https://example.com/missing") is None


def test_upsert_updates_content_but_keeps_first_seen(db):
    db.save_publication(_publication())

    with db.conn:
        first_seen = db.conn.execute(
            "SELECT first_seen FROM publications WHERE url = ?",
            ("https://example.com/rule/1",),
        ).fetchone()["first_seen"]

    db.save_publication(
        _publication(hash_value="hash-2", title="Updated title", impact_score=12)
    )

    row = db.conn.execute(
        "SELECT * FROM publications WHERE url = ?",
        ("https://example.com/rule/1",),
    ).fetchone()

    assert db.count_publications() == 1
    assert row["content_hash"] == "hash-2"
    assert row["title"] == "Updated title"
    assert row["impact_score"] == 12
    assert row["first_seen"] == first_seen


def test_upsert_keeps_previous_published_date_when_new_one_missing(db):
    db.save_publication(_publication())
    db.save_publication(_publication(published_date=None, hash_value="hash-2"))

    row = db.conn.execute(
        "SELECT published_date FROM publications"
    ).fetchone()

    assert row["published_date"].startswith("2026-10-20")


def test_mark_seen_updates_last_seen(db):
    db.save_publication(_publication())

    db.mark_seen("https://example.com/rule/1")

    row = db.conn.execute("SELECT last_seen FROM publications").fetchone()

    assert row["last_seen"] is not None


def test_recent_publications_filters_by_last_seen(db):
    db.save_publication(_publication())

    with db.conn:
        db.conn.execute(
            "UPDATE publications SET last_seen = ?",
            ("2020-01-01T00:00:00+00:00",),
        )

    assert db.recent_publications(30) == []


def test_run_lifecycle(db):
    run_id = db.start_run()
    db.finish_run(run_id, 3)

    row = db.conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()

    assert row["finished_at"] is not None
    assert row["publications_found"] == 3


def test_existing_database_is_migrated(tmp_path):
    path = tmp_path / "legacy.db"
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE publications (
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
        """
    )
    connection.commit()
    connection.close()

    database = Database(str(path))

    columns = {
        row["name"]
        for row in database.conn.execute("PRAGMA table_info(publications)")
    }

    database.close()

    assert "published_date" in columns
