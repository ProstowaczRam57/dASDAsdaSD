from typing import Dict

from regwatch.matching import KeywordMatcher


class ActionClassifier:
    """Classifies the regulatory action type mentioned in a text."""

    # Higher value = more significant action. Used to pick one action when a
    # page mentions several.
    ACTION_PRIORITY: Dict[str, int] = {
        "enacted_law": 100,
        "final_rule": 90,
        "proposed_rule": 80,
        "substance_update": 70,
        "scope_change": 60,
        "guidance": 50,
        "hearing_event": 45,
        "enforcement": 40,
        "postponement": 30,
        "amendment": 20,
    }

    def __init__(self, taxonomy: dict):
        self.rules = taxonomy.get("action_types") or {}
        self._matchers = {
            action: KeywordMatcher(keywords or [])
            for action, keywords in self.rules.items()
        }

    def classify(self, text: str) -> str:
        if not text:
            return "unknown"

        matches = [
            action
            for action, matcher in self._matchers.items()
            if matcher.first_match(text) is not None
        ]

        if not matches:
            return "unknown"

        return max(
            matches,
            key=lambda action: self.ACTION_PRIORITY.get(action, 0),
        )
