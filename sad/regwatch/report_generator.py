import csv
import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Mapping

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem; color: #1f2933; }}
    h1 {{ font-size: 1.5rem; }}
    .meta {{ color: #616e7c; margin-bottom: 1.5rem; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 0.9rem; }}
    th, td {{ border-bottom: 1px solid #e4e7eb; padding: 0.5rem; text-align: left; vertical-align: top; }}
    th {{ background: #f5f7fa; position: sticky; top: 0; }}
    tr.high td.severity {{ color: #b42318; font-weight: 600; }}
    tr.medium td.severity {{ color: #b54708; }}
    tr.low td.severity {{ color: #027a48; }}
    a {{ color: #1d4ed8; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <p class="meta">Generated {generated} &middot; {count} publications</p>
  <table>
    <thead>
      <tr>
        <th>Source</th>
        <th>Title</th>
        <th>Domain</th>
        <th>Topic</th>
        <th>Action</th>
        <th>Score</th>
        <th>Published</th>
        <th>Last seen</th>
      </tr>
    </thead>
    <tbody>
{rows}
    </tbody>
  </table>
</body>
</html>
"""

def severity_for_score(
    score: int,
    low_max: int = 5,
    medium_max: int = 10,
) -> str:
    if score <= low_max:
        return "low"

    if score <= medium_max:
        return "medium"

    return "high"


def _format_date(value: str) -> str:
    if not value:
        return ""

    try:
        parsed = datetime.fromisoformat(value)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return value


def _as_dict(row: Mapping) -> dict:
    return dict(row)


class ReportGenerator:
    """Writes HTML and CSV reports without extra dependencies."""

    def __init__(self, settings: dict, output_dir: Path):
        self.settings = settings
        self.output_dir = Path(output_dir)
        severity = settings.get("severity") or {}
        self.low_max = int(severity.get("low_max", 5))
        self.medium_max = int(severity.get("medium_max", 10))
        self.filename = str(
            (settings.get("reporting") or {}).get(
                "output_filename",
                "regulatory_report",
            )
        )

    def generate(self, publications: Iterable[Mapping]) -> List[Path]:
        rows = [_as_dict(row) for row in publications]
        reporting = self.settings.get("reporting") or {}
        written: List[Path] = []

        self.output_dir.mkdir(parents=True, exist_ok=True)

        if reporting.get("generate_html", True):
            written.append(self._write_html(rows))

        if reporting.get("generate_excel", True):
            # CSV opens directly in Excel and needs no third-party package.
            written.append(self._write_csv(rows))

        return written

    def _write_csv(self, rows: List[dict]) -> Path:
        path = self.output_dir / f"{self.filename}.csv"

        fieldnames = [
            "source_id",
            "title",
            "url",
            "domain",
            "topic",
            "action_type",
            "impact_score",
            "published_date",
            "first_seen",
            "last_seen",
        ]

        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=fieldnames,
                extrasaction="ignore",
            )
            writer.writeheader()

            for row in rows:
                writer.writerow(row)

        return path

    def _write_html(self, rows: List[dict]) -> Path:
        path = self.output_dir / f"{self.filename}.html"

        table_rows = []

        for row in rows:
            score = int(row.get("impact_score") or 0)
            severity = severity_for_score(score, self.low_max, self.medium_max)
            url = html.escape(str(row.get("url") or ""), quote=True)
            title = html.escape(str(row.get("title") or ""))

            table_rows.append(
                "      <tr class=\"{severity}\">\n"
                "        <td>{source}</td>\n"
                "        <td><a href=\"{url}\">{title}</a></td>\n"
                "        <td>{domain}</td>\n"
                "        <td>{topic}</td>\n"
                "        <td>{action}</td>\n"
                "        <td class=\"severity\">{score}</td>\n"
                "        <td>{published}</td>\n"
                "        <td>{last_seen}</td>\n"
                "      </tr>".format(
                    severity=severity,
                    source=html.escape(str(row.get("source_id") or "")),
                    url=url,
                    title=title,
                    domain=html.escape(str(row.get("domain") or "")),
                    topic=html.escape(str(row.get("topic") or "")),
                    action=html.escape(str(row.get("action_type") or "")),
                    score=score,
                    published=_format_date(str(row.get("published_date") or "")),
                    last_seen=_format_date(str(row.get("last_seen") or "")),
                )
            )

        path.write_text(
            HTML_TEMPLATE.format(
                title=html.escape(self.filename.replace("_", " ").title()),
                generated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                count=len(rows),
                rows="\n".join(table_rows) or "      <tr><td colspan=\"8\">No publications</td></tr>",
            ),
            encoding="utf-8",
        )

        return path
