import csv

from regwatch.report_generator import ReportGenerator


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
        "change_type": "UPDATED",
        "change_summary": "- Limit changed from 10 to 5 ppm.",
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
    assert "Limit changed from 10 to 5 ppm." in html

    with open(tmp_path / "regulatory_report.csv", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    assert rows[0]["topic"] == "pfas"
    assert rows[0]["change_type"] == "UPDATED"
    assert rows[0]["change_summary"].startswith("- Limit changed")


def test_empty_report_is_valid(tmp_path):
    written = ReportGenerator(SETTINGS, tmp_path).generate([])
    html = (tmp_path / "regulatory_report.html").read_text(encoding="utf-8")

    assert written
    assert "No publications" in html


def test_missing_summary_is_rendered_as_empty(tmp_path):
    rows = [dict(ROWS[0], change_type="NEW", change_summary=None)]

    ReportGenerator(SETTINGS, tmp_path).generate(rows)

    html = (tmp_path / "regulatory_report.html").read_text(encoding="utf-8")

    assert 'class="summary"></td>' in html
