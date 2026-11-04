import sqlite3
import zlib
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
        "body": "Final rule text.\nSecond paragraph.",
        "content_hash": "hash-1",
        "published_date": datetime(2026, 10, 20, tzinfo=timezone.utc),
        "domain": "environment",
        "topic": "pfas",
        "action_type": "final_rule",
        "change_type": "NEW",
    }
    values.update(overrides)
    return Publication(**values)


def test_save_and_get_state(db):
    db.save_publication(_publication())

    state = db.get_state("https://example.com/rule/1")

    assert state is not None
    assert state["content_hash"] == "hash-1"
    assert state["body"] == "Final rule text.\nSecond paragraph."
    assert db.get_hash("https://example.com/rule/1") == "hash-1"
    assert db.get_state("https://example.com/missing") is None


def test_body_is_stored_compressed(db):
    db.save_publication(_publication())

    row = db.conn.execute("SELECT body FROM publications").fetchone()

    assert isinstance(row["body"], bytes)
    assert zlib.decompress(row["body"]).decode("utf-8").startswith("Final rule")
    assert b"Final rule" not in row["body"]


def test_update_keeps_previous_body_and_hash(db):
    db.save_publication(_publication())

    db.save_publication(
        _publication(
            body="Amended rule text.",
            content_hash="hash-2",
            previous_body="Final rule text.\nSecond paragraph.",
            previous_hash="hash-1",
            change_type="UPDATED",
            change_summary="- Limit changed from 10 to 5 ppm.",
            title="Updated title",
        )
    )

    publication = db.get_publication("https://example.com/rule/1")

    assert db.count_publications() == 1
    assert publication["body"] == "Amended rule text."
    assert publication["previous_body"] == "Final rule text.\nSecond paragraph."
    assert publication["previous_hash"] == "hash-1"
    assert publication["content_hash"] == "hash-2"
    assert publication["change_type"] == "UPDATED"
    assert publication["change_summary"] == "- Limit changed from 10 to 5 ppm."
    assert publication["title"] == "Updated title"


def test_upsert_keeps_first_seen(db):
    db.save_publication(_publication())

    first_seen = db.conn.execute(
        "SELECT first_seen FROM publications"
    ).fetchone()["first_seen"]

    db.save_publication(_publication(content_hash="hash-2", change_type="UPDATED"))

    row = db.conn.execute("SELECT first_seen FROM publications").fetchone()

    assert row["first_seen"] == first_seen


def test_upsert_keeps_previous_published_date_when_new_one_missing(db):
    db.save_publication(_publication())
    db.save_publication(_publication(published_date=None, content_hash="hash-2"))

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

    for expected in (
        "published_date",
        "body",
        "previous_body",
        "previous_hash",
        "change_type",
        "change_summary",
        "summary_generated_at",
    ):
        assert expected in columns

    assert "impact_score" not in columns
