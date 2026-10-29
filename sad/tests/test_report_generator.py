import csv

from regwatch.report_generator import ReportGenerator, severity_for_score

SETTINGS = {
    "reporting": {
        "generate_html": True,
        "generate_excel": True,
        "output_filename": "regulatory_report",
    }
}


ROWS = [
    {
        "source_id": "ca_carb",
        "title": "PFAS <final> rule",
        "url": "https://example.com/rule?a=1&b=2",
        "domain": "environment",
        "topic": "pfas",
        "action_type": "final_rule",
        "impact_score": 12,
        "published_date": "2026-10-20T10:00:00+00:00",
        "first_seen": "2026-10-21T10:00:00+00:00",
        "last_seen": "2026-10-21T10:00:00+00:00",
    }
]


def test_generates_html_and_csv(tmp_path):
    written = ReportGenerator(SETTINGS, tmp_path).generate(ROWS)

    names = {path.name for path in written}

    assert names == {"regulatory_report.html", "regulatory_report.csv"}

    html = (tmp_path / "regulatory_report.html").read_text(encoding="utf-8")
    assert "PFAS &lt;final&gt; rule" in html
    assert "&amp;b=2" in html

    with open(tmp_path / "regulatory_report.csv", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["topic"] == "pfas"


def test_empty_report_is_valid(tmp_path):
    written = ReportGenerator(SETTINGS, tmp_path).generate([])
    html = (tmp_path / "regulatory_report.html").read_text(encoding="utf-8")

    assert written
    assert "No publications" in html


def test_severity_bands():
    assert severity_for_score(0) == "low"
    assert severity_for_score(5) == "low"
    assert severity_for_score(6) == "medium"
    assert severity_for_score(11) == "high"


def test_severity_uses_configured_thresholds(tmp_path):
    settings = {
        "reporting": {"output_filename": "report"},
        "severity": {"low_max": 1, "medium_max": 2},
    }
    rows = [dict(ROWS[0], impact_score=3)]

    ReportGenerator(settings, tmp_path).generate(rows)

    html = (tmp_path / "report.html").read_text(encoding="utf-8")

    assert 'class="high"' in html
