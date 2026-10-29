"""End-to-end run with a fake fetcher (no network access)."""

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


def test_run_saves_recent_publications(config_dir, tmp_path):
    stats = run(config_dir=str(config_dir), fetcher=FakeFetcher(_pages()))

    assert stats.sources_scanned == 1
    assert stats.new == 2  # article + about page
    assert stats.skipped_old == 1
    assert stats.errors == 0

    database = Database(str(tmp_path / "data" / "test.db"))
    assert database.count_publications() == 2
    database.close()

    assert (tmp_path / "data" / "reports" / "regulatory_report.html").exists()


def test_second_run_detects_no_changes(config_dir):
    run(config_dir=str(config_dir), fetcher=FakeFetcher(_pages()))

    stats = run(config_dir=str(config_dir), fetcher=FakeFetcher(_pages()))

    assert stats.new == 0
    assert stats.updated == 0
    assert stats.unchanged == 2


def test_modified_page_is_marked_updated(config_dir):
    run(config_dir=str(config_dir), fetcher=FakeFetcher(_pages()))

    stats = run(
        config_dir=str(config_dir),
        fetcher=FakeFetcher(_pages(text="Amended final rule on PFAS")),
    )

    assert stats.updated == 1
    assert stats.unchanged == 1


def test_dry_run_does_not_write(config_dir, tmp_path):
    stats = run(
        config_dir=str(config_dir),
        fetcher=FakeFetcher(_pages()),
        dry_run=True,
        generate_report=False,
    )

    assert stats.new == 2

    database = Database(str(tmp_path / "data" / "test.db"))
    assert database.count_publications() == 0
    database.close()


def test_source_filter_skips_other_sources(config_dir):
    stats = run(
        config_dir=str(config_dir),
        fetcher=FakeFetcher(_pages()),
        source_ids=["does-not-exist"],
    )

    assert stats.sources_scanned == 0
    assert stats.links_seen == 0


def test_impact_score_uses_settings_weights(config_dir):
    run(config_dir=str(config_dir), fetcher=FakeFetcher(_pages()))

    database = Database(str(config_dir.parent / "data" / "test.db"))
    row = database.conn.execute(
        "SELECT impact_score FROM publications WHERE url = ?",
        (ARTICLE_URL,),
    ).fetchone()
    database.close()

    assert row["impact_score"] > 0
