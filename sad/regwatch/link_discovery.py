from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
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
    "emission"
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
    "share="
]
def filter_priority_links(links):

    priority_links = []

    for link in links:

        link_lower = link.lower()

        if any(
            pattern in link_lower
            for pattern in PRIORITY_PATTERNS
        ):
            priority_links.append(link)

    return priority_links


def is_valid_link(link, base_domain):

    link = link.lower()

    for pattern in BLOCKED_PATTERNS:
        if pattern in link:
            return False

    if link.startswith("javascript:"):
        return False

    if link.startswith("#"):
        return False

    parsed = urlparse(link)

    # tylko ten sam domenowy serwis
    if parsed.netloc and base_domain not in parsed.netloc:
        return False

    return True


def discover_links(html, base_url):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    base_domain = urlparse(
        base_url
    ).netloc

    links = set()

    for a in soup.select("a[href]"):

        href = a.get("href")

        if not href:
            continue

        link = urljoin(
            base_url,
            href
        )

        if not is_valid_link(
            link,
            base_domain
        ):
            continue

        links.add(link)

    filtered_links = filter_priority_links(
        list(links)
    )

    if filtered_links:
        return filtered_links

    return list(links)