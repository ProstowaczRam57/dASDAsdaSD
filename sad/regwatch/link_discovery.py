import re
from typing import List, Optional, Set
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

PRIORITY_PATTERNS = [
    "rule",
    "rulemaking",
    "regulation",
    "register",
    "notice",
    "proposal",
    "proposed",
    "consultation",
    "hearing",
    "agenda",
    "bill",
    "legislation",
    "law",
    "statute",
    "guidance",
    "faq",
    "pfas",
    "chemical",
    "product",
    "packaging",
    "epr",
    "osha",
    "safety",
    "water",
    "air",
    "emission",
]

BLOCKED_PATTERNS = [
    # Social media
    "youtube.com",
    "youtu.be",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "tiktok.com",
    "flickr.com",
    "vimeo.com",
    "bsky.app",
    # Email / phone
    "mailto:",
    "tel:",
    # Oregon-specific noise
    "oregondeqblog",
    "deqblog",
    "bestvpn.org/oregon",
    "eplace",
    "edap",
    # Specific sites to skip
    "storymaps",
    "olis.oregonlegislature.gov",
    "turi.org",
    # Generic social sharing
    "facebook.com",
    "share?",
    "share=",
]

# Documents the parser cannot read; fetching them only produces errors.
BLOCKED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".zip",
    ".gz",
    ".rar",
    ".7z",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".css",
    ".js",
}

TRACKING_PARAM_PREFIXES = ("utm_",)
TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "referrer",
    "source",
}

HTML_EXTENSIONS = (".html", ".htm", ".shtml", ".php", ".aspx", ".asp", ".jsp")


def _host(url: str) -> str:
    return urlsplit(url).hostname or ""


def _registrable_host(host: str) -> str:
    return host.lower().removeprefix("www.")


def same_site(link_host: str, base_host: str) -> bool:
    """True for the same host or a subdomain of it.

    Deliberately not a substring check: ``evil-leginfo.legislature.ca.gov``
    must not be treated as part of ``leginfo.legislature.ca.gov``.
    """

    link = _registrable_host(link_host)
    base = _registrable_host(base_host)

    if not link or not base:
        return False

    return link == base or link.endswith("." + base)


def normalize_url(url: str) -> str:
    parts = urlsplit(url.strip())

    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()

    if not host:
        return ""

    if parts.username or parts.password:
        netloc = parts.netloc.lower()

    try:
        port = parts.port
    except ValueError:
        # Malformed port such as https://example.com:abc/
        return ""

    if port and port not in (80, 443):
        netloc = f"{host}:{port}"
    else:
        netloc = host

    path = parts.path or "/"

    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith(TRACKING_PARAM_PREFIXES)
        and key.lower() not in TRACKING_PARAMS
    ]

    query = urlencode(sorted(query_pairs), doseq=True)

    return urlunsplit((scheme, netloc, path, query, ""))


def _has_blocked_extension(path: str) -> bool:
    lowered = path.lower()
    return any(lowered.endswith(ext) for ext in BLOCKED_EXTENSIONS)


def is_valid_link(link: str, base_url: str) -> bool:
    if not link:
        return False

    lowered = link.lower()

    for pattern in BLOCKED_PATTERNS:
        if pattern in lowered:
            return False

    if lowered.startswith(("javascript:", "mailto:", "tel:", "data:")):
        return False

    if link.startswith("#"):
        return False

    parts = urlsplit(link)

    if parts.scheme not in {"http", "https"}:
        return False

    if not same_site(_host(link), _host(base_url)):
        return False

    if _has_blocked_extension(parts.path):
        return False

    return True


def _priority_score(link: str, anchor_text: str) -> int:
    """Only the path and anchor text decide priority.

    Checking the full URL would match the host itself (e.g. a domain that
    contains "law") and mark every link as important.
    """

    path = urlsplit(link).path.lower()
    text = (anchor_text or "").lower()

    haystack = f"{path} {text}"

    score = 0

    for pattern in PRIORITY_PATTERNS:
        if re.search(r"(?<!\w)" + re.escape(pattern), haystack):
            score += 1

    # Bonus for links that look like individual documents.
    if path.endswith(HTML_EXTENSIONS) or re.search(r"/\d{3,}", path):
        score += 1

    return score


def discover_links(
    html: str,
    base_url: str,
    max_links: Optional[int] = None,
) -> List[str]:
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")

    seen: Set[str] = set()
    scored: List[tuple] = []

    for anchor in soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()

        if not href:
            continue

        absolute = urljoin(base_url, href)
        normalized = normalize_url(absolute)

        if not normalized or normalized in seen:
            continue

        if not is_valid_link(normalized, base_url):
            continue

        # Ignore links pointing at the page itself.
        if normalize_url(base_url) == normalized:
            continue

        seen.add(normalized)

        anchor_text = anchor.get_text(" ", strip=True)
        scored.append((_priority_score(normalized, anchor_text), normalized))

    prioritized = [link for score, link in scored if score > 0]
    rest = [link for score, link in scored if score == 0]

    prioritized.sort()
    rest.sort()

    ordered = prioritized + rest

    if max_links is not None and max_links > 0:
        ordered = ordered[:max_links]

    return ordered
