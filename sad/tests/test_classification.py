from regwatch.action_classifier import ActionClassifier
from regwatch.config_loader import ConfigLoader
from regwatch.taxonomy_matcher import TaxonomyMatcher


def _taxonomy():
    return ConfigLoader().load_taxonomy()


def test_classify_pfas_topic():
    matcher = TaxonomyMatcher(_taxonomy())

    domain, topic = matcher.classify(
        "New PFAS restriction under REACH for food packaging"
    )

    assert domain == "environment"
    assert topic in {"pfas", "chemical_restrictions", "packaging"}


def test_unrelated_text_is_not_classified():
    matcher = TaxonomyMatcher(_taxonomy())

    assert matcher.classify("Our team had lunch and discussed holiday plans") == (
        None,
        None,
    )


def test_action_priority_prefers_enacted_law():
    classifier = ActionClassifier(_taxonomy())

    text = "Proposed rule open for consultation; the law was enacted today"

    assert classifier.classify(text) == "enacted_law"


def test_unknown_action():
    classifier = ActionClassifier(_taxonomy())

    assert classifier.classify("Seasonal greetings from the office") == "unknown"


def test_action_keywords_do_not_match_inside_words():
    classifier = ActionClassifier(_taxonomy())

    # "fine" used to match "definition"/"fine dining" via substring matching.
    assert classifier.classify("The fine dining event was refined") == "unknown"
