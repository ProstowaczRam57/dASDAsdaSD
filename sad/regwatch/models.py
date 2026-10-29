from dataclasses import dataclass
from typing import Optional


@dataclass
class Source:

    id: str
    name: str

    jurisdiction: str

    state: Optional[str]

    category: str

    type: str

    url: str

    enabled: bool


@dataclass
class Publication:

    source_id: str

    source_name: str

    title: str

    url: str

    content: str

    hash_value: str

    action_type: str = ""

    domain: str = ""

    topic: str = ""

    impact_score: int = 0

    change_type: str = ""
