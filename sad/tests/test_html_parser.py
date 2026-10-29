from datetime import timezone

import pytest
from regwatch.html_parser import HtmlParser


def test_extract_title_prefers_title_tag():
    parser = HtmlParser()

    assert parser.extract_title("<html><title>Rule 42</title><h1>Other</h1></html>") == "Rule 42"


def test_title_falls_back_to_h1_and_default():
    parser = HtmlParser()

    assert parser.extract_title("<html><body><h1>Heading</h1></body></html>") == "Heading"
    assert parser.extract_title("<html><body><p>none</p></body></html>") == "Unknown Title"


def test_extract_text_drops_boilerplate():
    parser = HtmlParser()
    html = """
    <html><body>
      <nav>Home | About</nav>
      <script>var x = 1;</script>
      <p>Final   rule text</p>
      <footer>Copyright</footer>
    </body></html>
    """

    assert parser.extract_text(html) == "Final rule text"


def test_extract_date_from_meta_is_timezone_aware():
    parser = HtmlParser()
    html = '<meta property="article:published_time" content="2026-10-20T10:00:00Z">'

    parsed = parser.extract_date(html)

    assert parsed is not None
    assert parsed.isoformat() == "2026-10-20T10:00:00+00:00"
    assert parsed.tzinfo is not None


def test_extract_date_from_json_ld():
    parser = HtmlParser()
    html = """
    <script type="application/ld+json">
    {"@type": "NewsArticle", "datePublished": "2026-09-01"}
    </script>
    """

    parsed = parser.extract_date(html)

    assert parsed is not None
    assert parsed.year == 2026 and parsed.month == 9


def test_extract_date_from_time_tag():
    parser = HtmlParser()

    parsed = parser.extract_date('<time datetime="2026-01-02">January 2</time>')

    assert parsed is not None
    assert parsed.day == 2


def test_extract_date_from_text_fallback():
    parser = HtmlParser()

    parsed = parser.extract_date("<p>Published on 2026-03-04 by the agency</p>")

    assert parsed is not None
    assert parsed.month == 3 and parsed.day == 4


def test_invalid_meta_date_falls_through():
    parser = HtmlParser()
    html = (
        '<meta name="date" content="not a date">'
        "<time datetime='2026-05-06'>May 6</time>"
    )

    parsed = parser.extract_date(html)

    assert parsed is not None
    assert parsed.month == 5


def test_empty_html_raises():
    parser = HtmlParser()

    with pytest.raises(ValueError):
        parser.extract_text("")


def test_naive_fallback_date_is_utc():
    parser = HtmlParser()

    parsed = parser.extract_date("<p>2026-08-09</p>")

    assert parsed is not None
    assert parsed.tzinfo == timezone.utc
