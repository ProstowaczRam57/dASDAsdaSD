"""End-to-end run with fake fetcher/summarizer (no network access)."""

import shutil
from datetime import datetime, timedelta, timezone

import pytest
import yaml

from regwatch.config_loader import DEFAULT_CONFIG_DIR
from regwatch.db import Database
from regwatch.main import run

SOURCE_URL = "https://example.gov/rulemaking"
ARTICLE_URL = "https://example.gov/rulemaking/1"
OLD_URL = "https://example.gov/rulemaking/2"

LISTING_HTML = f"""
<html><body>
  <a href="{ARTICLE_URL}">Proposed PFAS rule</a>
  <a href="{OLD_URL}">Old air rule</a>
  <a href="https://example.gov/about">About</a>
</body></html>
"""


def _article(text, published):
    return f"""
    <html><head>
      <title>PFAS rule</title>
      <meta property="article:published_time" content="{published}">
    </head><body><p>{text}</p></body></html>
    """


class FakeFetcher:
    def __init__(self, pages):
        self.pages = pages
        self.requested = []

    def get(self, url):
        self.requested.append(url)

        if url not in self.pages:
            raise AssertionError(f"Unexpected URL fetched: {url}")

        return self.pages[url]

    def close(self):
        pass


class FakeSummarizer:
    def __init__(self, summary="- Rule text changed.", requires=True):
        self.summary = summary
        self.requires_summary = requires
        self.calls = []

    def summarize(self, old_body, new_body, title, url):
        self.calls.append(
            {
                "old": old_body,
                "new": new_body,
                "title": title,
                "url": url,
            }
        )
        return self.summary

    def close(self):
        pass


@pytest.fixture()
def config_dir(tmp_path):
    target = tmp_path / "config"
    shutil.copytree(DEFAULT_CONFIG_DIR, target)

    settings = yaml.safe_load((target / "settings.yaml").read_text(encoding="utf-8"))
    settings["database"]["path"] = "data/test.db"
    settings["logging"]["file"] = "data/test.log"
    (target / "settings.yaml").write_text(
        yaml.safe_dump(settings, sort_keys=False),
        encoding="utf-8",
    )

    sources = {
        "request_delay_s": 0,
        "default_tracking": {"max_subpages": 10},
        "sources": [
            {
                "id": "example",
                "name": "Example Agency",
                "jurisdiction": "US",
                "state": None,
                "category": "environment",
                "type": "page",
                "url": SOURCE_URL,
                "enabled": True,
            }
        ],
    }
    (target / "sources.yaml").write_text(
        yaml.safe_dump(sources, sort_keys=False),
        encoding="utf-8",
    )

    return target


def _pages(text="Final rule on PFAS restrictions", recent=None):
    published = recent or (datetime.now(timezone.utc) - timedelta(days=2))

    return {
        SOURCE_URL: LISTING_HTML,
        ARTICLE_URL: _article(text, published.isoformat()),
        OLD_URL: _article("Old rule", "2020-01-01T00:00:00+00:00"),
        "https://example.gov/about": _article("About", published.isoformat()),
    }


def _database(tmp_path):
    path = tmp_path / "data" / "test.db"
    path.parent.mkdir(parents=True, exist_ok=True)

    return Database(str(path))


def _publication_row(tmp_path, url=ARTICLE_URL):
    database = _database(tmp_path)
    publication = database.get_publication(url)
    database.close()

    return publication


def test_run_stores_bodies(config_dir, tmp_path):
    stats = run(
        config_dir=str(config_dir),
        fetcher=FakeFetcher(_pages()),
        summarizer=FakeSummarizer(),
    )

    assert stats.sources_scanned == 1
    assert stats.new == 2  # article + about page
    assert stats.skipped_old == 1
    assert stats.errors == 0

    publication = _publication_row(tmp_path)

    assert publication["body"].startswith("Final rule on PFAS")
    assert publication["previous_body"] == ""
    assert publication["change_type"] == "NEW"
    assert publication["change_summary"] is None

    assert (tmp_path / "data" / "reports" / "regulatory_report.html").exists()


def test_second_run_detects_no_changes(config_dir):
    summarizer = FakeSummarizer()

    run(
        config_dir=str(config_dir),
        fetcher=FakeFetcher(_pages()),
        summarizer=summarizer,
    )
    stats = run(
        config_dir=str(config_dir),
        fetcher=FakeFetcher(_pages()),
        summarizer=summarizer,
    )

    assert stats.new == 0
    assert stats.updated == 0
    assert stats.unchanged == 2
    assert summarizer.calls == []


def test_modified_page_keeps_old_body_and_stores_summary(config_dir, tmp_path):
    run(
        config_dir=str(config_dir),
        fetcher=FakeFetcher(_pages()),
        summarizer=FakeSummarizer(),
    )
    original = _publication_row(tmp_path)

    summarizer = FakeSummarizer("- PFAS limit changed from 10 to 5 ppm.")
    stats = run(
        config_dir=str(config_dir),
        fetcher=FakeFetcher(_pages(text="Amended final rule on PFAS")),
        summarizer=summarizer,
    )

    assert stats.updated == 1
    assert stats.summarized == 1
    assert stats.unchanged == 1
    assert len(summarizer.calls) == 1

    call = summarizer.calls[0]
    assert call["old"] == original["body"]
    assert call["new"].startswith("Amended final rule on PFAS")
    assert call["url"] == ARTICLE_URL

    updated = _publication_row(tmp_path)

    assert updated["body"] == call["new"]
    assert updated["previous_body"] == original["body"]
    assert updated["previous_hash"] == original["content_hash"]
    assert updated["change_summary"] == "- PFAS limit changed from 10 to 5 ppm."
    assert updated["summary_generated_at"] is not None


def test_failed_summary_keeps_previous_body(config_dir, tmp_path):
    run(
        config_dir=str(config_dir),
        fetcher=FakeFetcher(_pages()),
        summarizer=FakeSummarizer(),
    )
    original = _publication_row(tmp_path)

    stats = run(
        config_dir=str(config_dir),
        fetcher=FakeFetcher(_pages(text="Amended final rule on PFAS")),
        summarizer=FakeSummarizer(summary=None),
    )

    assert stats.updated == 0
    assert stats.errors == 1

    unchanged = _publication_row(tmp_path)

    assert unchanged["body"] == original["body"]
    assert unchanged["content_hash"] == original["content_hash"]
    assert unchanged["change_summary"] is None


def test_update_without_ai_still_replaces_body(config_dir, tmp_path):
    run(
        config_dir=str(config_dir),
        fetcher=FakeFetcher(_pages()),
        summarizer=FakeSummarizer(),
    )
    original = _publication_row(tmp_path)

    stats = run(
        config_dir=str(config_dir),
        fetcher=FakeFetcher(_pages(text="Amended final rule on PFAS")),
        summarizer=FakeSummarizer(summary=None, requires=False),
    )

    assert stats.updated == 1
    assert stats.errors == 0

    updated = _publication_row(tmp_path)

    assert updated["body"] != original["body"]
    assert updated["previous_body"] == original["body"]
    assert updated["change_summary"] is None


def test_dry_run_does_not_call_ai(config_dir):
    summarizer = FakeSummarizer()

    run(
        config_dir=str(config_dir),
        fetcher=FakeFetcher(_pages()),
        summarizer=summarizer,
        dry_run=True,
        generate_report=False,
    )
    run(
        config_dir=str(config_dir),
        fetcher=FakeFetcher(_pages(text="Changed text")),
        summarizer=summarizer,
        dry_run=True,
        generate_report=False,
    )

    assert summarizer.calls == []


def test_legacy_row_without_body_is_revisited(config_dir, tmp_path):
    database = _database(tmp_path)
    database.conn.execute(
        """
        INSERT INTO publications (
            source_id, title, url, content_hash, first_seen, last_seen
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            "example",
            "Old title",
            ARTICLE_URL,
            "stale-hash-without-body",
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
        ),
    )
    database.conn.commit()
    database.close()

    stats = run(
        config_dir=str(config_dir),
        fetcher=FakeFetcher(_pages()),
        summarizer=FakeSummarizer(),
    )

    publication = _publication_row(tmp_path)

    assert stats.new == 2
    assert publication["body"].startswith("Final rule on PFAS")
    assert publication["content_hash"] != "stale-hash-without-body"


def test_dry_run_does_not_write(config_dir, tmp_path):
    stats = run(
        config_dir=str(config_dir),
        fetcher=FakeFetcher(_pages()),
        summarizer=FakeSummarizer(),
        dry_run=True,
        generate_report=False,
    )

    assert stats.new == 2

    database = _database(tmp_path)
    assert database.count_publications() == 0
    database.close()


def test_source_filter_skips_other_sources(config_dir):
    stats = run(
        config_dir=str(config_dir),
        fetcher=FakeFetcher(_pages()),
        summarizer=FakeSummarizer(),
        source_ids=["does-not-exist"],
    )

    assert stats.sources_scanned == 0
    assert stats.links_seen == 0
