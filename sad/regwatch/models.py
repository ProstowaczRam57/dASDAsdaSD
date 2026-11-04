from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Source:
    """A monitored regulatory source, as defined in config/sources.yaml."""

    id: str
    name: str
    jurisdiction: str
    category: str
    type: str
    url: str
    state: Optional[str] = None
    enabled: bool = True


@dataclass
class Publication:
    """A single publication discovered on a source page.

    ``body`` is the current page text. On an update ``previous_body`` keeps
    the text that was stored before, so both versions can be compared and
    summarised.
    """

    source_id: str
    source_name: str
    title: str
    url: str
    body: str = ""
    content_hash: str = ""
    previous_body: Optional[str] = None
    previous_hash: Optional[str] = None
    published_date: Optional[datetime] = None
    action_type: str = ""
    domain: str = ""
    topic: str = ""
    change_type: str = ""
    change_summary: Optional[str] = None
    summary_generated_at: Optional[datetime] = None
