# Regulatory Monitor (regwatch)

A small, dependency-light crawler that watches regulatory websites, stores the
text of every page, detects when a page changes, and asks an AI model to
summarise what changed. Results are kept in SQLite and exported to HTML/CSV.

## How it works

1. A source page is fetched and its links are followed (same host only).
2. For every page the title, text and publication date are extracted.
3. The text is stored in `publications.body` (zlib-compressed BLOB).
4. The SHA-256 hash is compared with the previous run:
   - **NEW** – first time seen, body is stored.
   - **UNCHANGED** – only `last_seen` is updated.
   - **UPDATED** – the previous body is passed to the AI together with the new
     body, the model writes a 2–5 bullet summary, and only then is the stored
     body replaced. The old text is kept in `publications.previous_body`.
5. Summaries are stored in `publications.change_summary` and included in the
   reports.

If the AI is enabled but a summary cannot be produced, the old body is **not**
replaced; the update is retried on the next run. If no API key is configured
(the `ai.enabled` flag or the environment variable is missing), summaries are
skipped and bodies are still updated normally.

## Requirements

- Python 3.10+
- Network access to the configured sources
- An OpenAI-compatible API key for change summaries (optional)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OPENAI_API_KEY="sk-..."     # optional, for AI summaries
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
| `--dry-run` | Do not write publications, runs, reports or call the AI |
| `--no-report` | Skip report generation |
| `--verbose` | Debug logging and tracebacks |

Exit codes: `0` success, `1` finished with crawl/AI errors, `2` invalid
configuration.

## Sources

All scraped sites live in **`sad/config/sources.yaml`**, under the `sources:`
key (after `default_tracking:`). Each entry looks like this:

```yaml
  - id: ca_carb_rulemaking
    name: California Air Resources Board Rulemaking
    jurisdiction: US-CA
    state: CA
    type: page
    category: air_emissions
    url: https://ww2.arb.ca.gov/rulemaking
    enabled: true
```

To test a single site you can either:

- comment out the other entries (prefix every line of the block with `#`), or
- keep the file untouched and run `python -m regwatch.main --source ca_carb_rulemaking`.

`--source` is safer: it does not require editing YAML and can be repeated.

## Configuration

- `sad/config/settings.yaml` – timeouts, retries, user agent, database path,
  lookback window, AI and reporting options.
- `sad/config/sources.yaml` – sources to monitor, request delay and tracking
  defaults (`max_subpages`, `compare_mode`).
- `sad/config/taxonomy.yaml` – domain/topic keywords and action-type keywords.
  Keywords ending with `*` match word prefixes (`emisj*`), all others must
  match a whole word. Polish and English keywords are supported.

### AI summaries

```yaml
ai:
  enabled: true
  base_url: https://api.openai.com/v1
  model: gpt-4o-mini
  api_key_env: OPENAI_API_KEY
  timeout_s: 90
  max_body_chars: 12000
  max_output_tokens: 400
  temperature: 0.2
```

Any OpenAI-compatible `/chat/completions` endpoint works (OpenAI, Azure
OpenAI-compatible gateways, local vLLM, etc.). The key is read only from the
environment variable named by `api_key_env`; it is never written to config or
to the database. Bodies longer than `max_body_chars` are shortened (head and
tail kept) before being sent.

Relative paths in `settings.yaml` are resolved against the repository root
(or the parent of `--config-dir`), so the tool can be started from anywhere.

## Output

- SQLite database (`sad/data/state.db` by default). The `publications` table
  keeps one row per URL:
  - `body`, `previous_body` – zlib-compressed current and previous page text
  - `content_hash`, `previous_hash` – SHA-256 of each version
  - `change_type`, `change_summary`, `summary_generated_at`
  - `source_id`, `title`, `url`, `domain`, `topic`, `action_type`,
    `published_date`, `first_seen`, `last_seen`
- `sad/data/reports/regulatory_report.html` and `.csv`: publications seen in
  the lookback window, with the AI change summary.
- `sad/logs/regulatory_monitor.log`: run log.

A run is recorded in the `runs` table even when no publications are found.

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The test suite is fully offline; HTTP and AI calls are faked.

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
    summarizer.py   old/new body comparison via an AI model
    db.py           SQLite schema, bodies, upsert, migrations
    state_manager.py
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
- One previous body is kept per page (not a full history).
