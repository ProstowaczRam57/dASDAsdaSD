from typing import Dict, List, Optional, Tuple

from regwatch.matching import KeywordMatcher


class TaxonomyMatcher:
    """Maps text to a (domain, topic) pair using config/taxonomy.yaml."""

    def __init__(self, taxonomy: dict):
        self.domains = taxonomy.get("domains") or {}
        self._matchers: Dict[Tuple[str, str], KeywordMatcher] = {}

        for domain, topics in self.domains.items():
            if not isinstance(topics, dict):
                continue

            for topic, keywords in topics.items():
                self._matchers[(domain, topic)] = KeywordMatcher(keywords or [])

    def classify(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        if not text:
            return None, None

        best_score = 0
        best_keyword_length = 0
        best_domain: Optional[str] = None
        best_topic: Optional[str] = None

        for (domain, topic), matcher in self._matchers.items():
            matched: List[str] = matcher.matches(text)

            if not matched:
                continue

            score = len(matched)
            keyword_length = max(len(keyword.rstrip("*")) for keyword in matched)

            # More matched keywords win; a longer keyword breaks ties, which
            # favours "occupational exposure limit" over "limit".
            if (score, keyword_length) > (best_score, best_keyword_length):
                best_score = score
                best_keyword_length = keyword_length
                best_domain = domain
                best_topic = topic

        return best_domain, best_topic

    def score(self, text: str, domain: str, topic: str) -> int:
        matcher = self._matchers.get((domain, topic))

        if matcher is None or not text:
            return 0

        return len(matcher.matches(text))
