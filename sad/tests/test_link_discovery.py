"""Link discovery is domain-scoped and must not follow lookalike hosts."""

from regwatch.link_discovery import (
    discover_links,
    is_valid_link,
    normalize_url,
    same_site,
)

BASE = "https://leginfo.legislature.ca.gov/"


def test_same_site_accepts_root_and_subdomains():
    assert same_site("leginfo.legislature.ca.gov", "leginfo.legislature.ca.gov")
    assert same_site("www.leginfo.legislature.ca.gov", "leginfo.legislature.ca.gov")
    assert same_site("api.leginfo.legislature.ca.gov", "leginfo.legislature.ca.gov")


def test_same_site_rejects_lookalike_hosts():
    assert not same_site("evil-leginfo.legislature.ca.gov", "leginfo.legislature.ca.gov")
    assert not same_site("leginfo.legislature.ca.gov.evil.com", "leginfo.legislature.ca.gov")
    assert not same_site("example.com", "leginfo.legislature.ca.gov")


def test_normalize_url_strips_fragment_and_tracking():
    normalized = normalize_url(
        "HTTPS://WWW.Example.COM:443/a?utm_source=news&b=2&a=1#section"
    )

    assert normalized == "https://www.example.com/a?a=1&b=2"


def test_invalid_links_are_rejected():
    for link in (
        "mailto:test@example.com",
        "tel:+123",
        "javascript:alert(1)",
        "#anchor",
        "https://leginfo.legislature.ca.gov/report.pdf",
        "https://youtube.com/watch?v=1",
        "https://evil-leginfo.legislature.ca.gov/",
    ):
        assert not is_valid_link(link, BASE), link


def test_discover_links_prioritizes_and_deduplicates():
    html = """
    <a href="/about">About the office</a>
    <a href="/rulemaking/123">Proposed rule 123</a>
    <a href="/rulemaking/123#top">Same rule, fragment</a>
    <a href="/about">Duplicate</a>
    <a href="https://leginfo.legislature.ca.gov/">Self</a>
    """

    links = discover_links(html, BASE)

    assert links[0] == "https://leginfo.legislature.ca.gov/rulemaking/123"
    assert links.count("https://leginfo.legislature.ca.gov/about") == 1
    assert len(links) == 2


def test_max_links_is_respected():
    html = "".join(f'<a href="/rule/{i}">Rule {i}</a>' for i in range(10))

    assert len(discover_links(html, BASE, max_links=3)) == 3
    assert len(discover_links(html, BASE, max_links=0)) == 10


def test_malformed_port_is_ignored():
    assert normalize_url("https://example.com:abc/rule") == ""
    assert discover_links('<a href="https://example.com:abc/x">x</a>', BASE) == []


def test_empty_html_returns_no_links():
    assert discover_links("", BASE) == []


def test_translated_copies_are_dropped_when_english_exists():
    html = """
    <a href="/rulemaking">Rulemaking</a>
    <a href="/es/rulemaking">Reglamentación</a>
    <a href="/zh/rulemaking">法规</a>
    """

    links = discover_links(html, BASE)

    assert links == ["https://leginfo.legislature.ca.gov/rulemaking"]


def test_translated_only_page_is_kept():
    html = '<a href="/es/rulemaking">Reglamentación</a>'

    links = discover_links(html, BASE)

    assert links == ["https://leginfo.legislature.ca.gov/es/rulemaking"]


def test_translated_copy_of_the_source_page_is_dropped():
    html = '<a href="/es/rulemaking">Reglamentación</a>'

    links = discover_links(html, "https://leginfo.legislature.ca.gov/rulemaking")

    assert links == []


def test_translated_copy_with_query_string_is_dropped():
    html = """
    <a href="/rulemaking?id=7">Rule</a>
    <a href="/es/rulemaking?id=7">Regla</a>
    """

    links = discover_links(html, BASE)

    assert links == ["https://leginfo.legislature.ca.gov/rulemaking?id=7"]
