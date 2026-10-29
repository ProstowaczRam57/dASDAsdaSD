from typing import Optional

from regwatch.models import Publication


class ImpactScorer:
    """Computes impact_score from the weights in settings.yaml."""

    def __init__(self, settings: dict):
        scoring = settings.get("scoring") or {}

        self.action_weights = scoring.get("action_weights") or {}
        self.topic_weights = scoring.get("topic_weights") or {}

    def score(
        self,
        publication: Publication,
        change_type: Optional[str] = None,
    ) -> int:
        action_weight = int(
            self.action_weights.get(publication.action_type, 0)
        )
        topic_weight = int(
            self.topic_weights.get(publication.topic, 0)
        )

        score = action_weight + topic_weight

        change = change_type or publication.change_type

        # A brand new publication matters more than a re-crawl of a known one.
        if change == "UPDATED":
            score += 1

        return score
