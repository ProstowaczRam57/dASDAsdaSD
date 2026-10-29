import json
import re
from datetime import datetime
from typing import Iterable, Optional

from bs4 import BeautifulSoup
from dateutil.parser import ParserError
from dateutil.parser import parse as parse_datetime
from regwatch.date_filter import to_utc

META_DATE_FIELDS = (
    "article:published_time",
    "article:modified_time",
    "datepublished",
    "datecreated",
    "publication_date",
    "publish-date",
    "publish_date",
    "date",
    "dc.date",
    "dc.date.issued",
    "dcterms.created",
)

DATE_PATTERNS = (
    r"\b\d{4}-\d{2}-\d{2}\b",
    r"\b\d{1,2}/\d{1,2}/\d{4}\b",
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b",
)

BOILERPLATE_TAGS = (
    "script",
    "style",
    "noscript",
    "nav",
    "footer",
    "header",
    "aside",
    "form",
    "svg",
)

MIN_YEAR = 1990
MAX_YEAR = 2100


def _safe_parse(value: object) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None

    cleaned = value.strip().replace("\u200b", "")

    if not cleaned:
        return None

    try:
        parsed = parse_datetime(cleaned)
    except (ParserError, ValueError, OverflowError, TypeError):
        return None

    if not MIN_YEAR <= parsed.year <= MAX_YEAR:
        return None

    return to_utc(parsed)


class HtmlParser:
    """Extracts title, text and publication date from an HTML document."""

    def __init__(self, strip_boilerplate: bool = True):
        self.strip_boilerplate = strip_boilerplate

    def _soup(self, html: str) -> BeautifulSoup:
        if not isinstance(html, str) or not html.strip():
            raise ValueError("HTML content is empty")

        return BeautifulSoup(html, "html.parser")

    def extract_text(self, html: str) -> str:
        soup = self._soup(html)

        tags = BOILERPLATE_TAGS if self.strip_boilerplate else (
            "script",
            "style",
            "noscript",
        )

        for tag in soup(list(tags)):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)

        return re.sub(r"\s+", " ", text).strip()

    def extract_title(self, html: str) -> str:
        soup = self._soup(html)

        if soup.title and soup.title.get_text(strip=True):
            return soup.title.get_text(strip=True)

        og_title = soup.find("meta", attrs={"property": "og:title"})

        if og_title and og_title.get("content"):
            return str(og_title["content"]).strip()

        h1 = soup.find("h1")

        if h1 and h1.get_text(strip=True):
            return h1.get_text(strip=True)

        return "Unknown Title"

    def _date_from_meta(self, soup: BeautifulSoup) -> Optional[datetime]:
        for field in META_DATE_FIELDS:
            field = field.lower()

            for meta in soup.find_all("meta"):
                prop = (
                    meta.get("property")
                    or meta.get("name")
                    or meta.get("itemprop")
                )

                if not prop or str(prop).lower() != field:
                    continue

                parsed = _safe_parse(meta.get("content"))

                if parsed is not None:
                    return parsed

        return None

    def _date_from_time_tags(self, soup: BeautifulSoup) -> Optional[datetime]:
        for time_tag in soup.find_all("time"):
            parsed = _safe_parse(
                time_tag.get("datetime") or time_tag.get_text(strip=True)
            )

            if parsed is not None:
                return parsed

        return None

    def _date_from_json_ld(self, soup: BeautifulSoup) -> Optional[datetime]:
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                payload = json.loads(script.string or "")
            except (json.JSONDecodeError, TypeError):
                continue

            for value in self._json_ld_dates(payload):
                parsed = _safe_parse(value)

                if parsed is not None:
                    return parsed

        return None

    def _json_ld_dates(self, payload: object) -> Iterable[str]:
        if isinstance(payload, dict):
            for key, value in payload.items():
                if key.lower() in {"datepublished", "datecreated", "datemodified"}:
                    if isinstance(value, str):
                        yield value

                yield from self._json_ld_dates(value)

        elif isinstance(payload, list):
            for item in payload:
                yield from self._json_ld_dates(item)

    def _date_from_text(self, text: str) -> Optional[datetime]:
        for pattern in DATE_PATTERNS:
            for match in re.findall(pattern, text):
                parsed = _safe_parse(match)

                if parsed is not None:
                    return parsed

        return None

    def extract_date(self, html: str) -> Optional[datetime]:
        soup = self._soup(html)

        for extractor in (
            self._date_from_meta,
            self._date_from_time_tags,
            self._date_from_json_ld,
        ):
            parsed = extractor(soup)

            if parsed is not None:
                return parsed

        # Do not treat dates inside inline scripts/styles as publication dates.
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        text = soup.get_text(" ", strip=True)

        return self._date_from_text(text)
