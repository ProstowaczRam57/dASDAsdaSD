import re
from typing import Iterable, List, Optional, Pattern, Tuple

# A keyword ending with "*" matches every word starting with that stem:
#   "emisj*" -> "emisja", "emisje", "emisjami", ...
# Everything else must match a whole word, so "EPR" no longer matches
# "representative" and "law" no longer matches "flawless".


def compile_keyword(keyword: str) -> Optional[Pattern[str]]:
    if not isinstance(keyword, str):
        return None

    original = keyword.strip()
    normalized = original.lower()

    if not normalized:
        return None

    is_prefix = normalized.endswith("*")
    stem = normalized[:-1].strip() if is_prefix else normalized

    if not stem:
        return None

    if is_prefix:
        suffix = r"\w*"
    elif original.replace(".", "").replace("-", "").isupper():
        # Acronyms are commonly pluralised: VOC/VOCs, EPR/EPRs.
        suffix = r"s?(?!\w)"
    else:
        suffix = r"(?!\w)"

    try:
        return re.compile(r"(?<!\w)" + re.escape(stem) + suffix)
    except re.error:
        return None


class KeywordMatcher:
    """Compiles keyword lists once and reports which ones occur in a text."""

    def __init__(self, keywords: Iterable[str]):
        self.patterns: List[Tuple[str, Pattern[str]]] = []

        for keyword in keywords:
            pattern = compile_keyword(keyword)

            if pattern is not None:
                self.patterns.append((keyword.lower(), pattern))

    def matches(self, text: str) -> List[str]:
        lowered = text.lower()

        return [
            keyword
            for keyword, pattern in self.patterns
            if pattern.search(lowered)
        ]

    def first_match(self, text: str) -> Optional[str]:
        lowered = text.lower()

        for keyword, pattern in self.patterns:
            if pattern.search(lowered):
                return keyword

        return None
