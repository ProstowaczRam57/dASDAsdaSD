# Regulatory Monitor (regwatch)

A small, dependency-light crawler that watches regulatory websites, detects new
and changed publications, classifies them by domain/topic and action type,
stores them in SQLite and produces HTML/CSV reports.

## Requirements

- Python 3.10+
- Network access to the configured sources

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

Run from the `sad/` directory:

```bash
cd sad
python -m regwatch.main
```

Or from the repository root:

```bash
python -m sad
```

Useful options:

```bash
python -m regwatch.main --dry-run              # crawl + classify, write nothing
python -m regwatch.main --source ca_carb_rulemaking
python -m regwatch.main --lookback-days 7 --max-links 10
python -m regwatch.main --no-report --verbose
python -m regwatch.main --config-dir /path/to/config
```

| Option | Description |
| --- | --- |
| `--config-dir` | Directory containing `settings.yaml`, `sources.yaml`, `taxonomy.yaml` |
| `--lookback-days` | Override `monitoring.lookback_days` for this run |
| `--max-links` | Links followed per source (`0` = unlimited, default 50) |
| `--source ID` | Only scan this source id (repeatable) |
| `--dry-run` | Do not write publications, runs or reports |
| `--no-report` | Skip report generation |
| `--verbose` | Debug logging and tracebacks |

Exit codes: `0` success, `1` finished with crawl errors, `2` invalid
configuration.

## Configuration

- `sad/config/settings.yaml` – timeouts, retries, user agent, database path,
  lookback window, scoring/severity weights and reporting options.
- `sad/config/sources.yaml` – sources to monitor, request delay and tracking
  defaults (`max_subpages`, `compare_mode`).
- `sad/config/taxonomy.yaml` – domain/topic keywords and action-type keywords.
  Keywords ending with `*` match word prefixes (`emisj*`), all others must
  match a whole word. Polish and English keywords are supported.

Relative paths in `settings.yaml` are resolved against the repository root
(or the parent of `--config-dir`), so the tool can be started from anywhere.

## Output

- SQLite database (`sad/data/state.db` by default): one row per URL with the
  content hash, classification, impact score, publication date, `first_seen`
  and `last_seen`.
- `sad/data/reports/regulatory_report.html` and `.csv`: publications seen in
  the lookback window, ranked by impact score.
- `sad/logs/regulatory_monitor.log`: run log.

A run is recorded in the `runs` table even when no publications are found.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The test suite is fully offline; HTTP access is faked.

## Project layout

```
sad/
  config/           YAML configuration
  regwatch/
    main.py         CLI and crawl loop
    config_loader.py
    fetcher.py      HTTP retries, throttling, content-type checks
    link_discovery.py
    html_parser.py  title/text/date extraction
    taxonomy_matcher.py
    action_classifier.py
    matching.py     word-boundary/prefix keyword matching
    publication_detector.py
    db.py           SQLite schema, upsert, migrations
    state_manager.py
    scoring.py
    report_generator.py
  tests/            offline pytest suite
```

## Known limitations

- Only `type: page` sources are implemented. `rss`, `json` and `html` sources
  are rejected with a warning.
- Links are followed only within the same host/subdomain of the source URL.
- PDFs and binary documents are skipped (no text extraction).
- JavaScript-rendered pages are not supported; a source that renders content
  client-side may yield little text.
- `monitoring.detect.removed_publications` is not implemented yet.
