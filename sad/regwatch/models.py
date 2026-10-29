from dataclasses import dataclass, field
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
    """A single publication discovered on a source page."""

    source_id: str
    source_name: str
    title: str
    url: str
    content: str = ""
    hash_value: str = ""
    published_date: Optional[datetime] = None
    action_type: str = ""
    domain: str = ""
    topic: str = ""
    impact_score: int = 0
    change_type: str = ""
    metadata: dict = field(default_factory=dict)
