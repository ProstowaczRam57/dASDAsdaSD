import pytest
from regwatch.matching import KeywordMatcher, compile_keyword


@pytest.mark.parametrize(
    "keyword,text,expected",
    [
        ("EPR", "EPR scheme for packaging", True),
        ("EPR", "a representative sample", False),
        ("law", "new law adopted", True),
        ("law", "flawless execution", False),
        ("emisj*", "nowa emisja gazów", True),
        ("emisj*", "emisje i emisjami", True),
        ("carbon credit*", "carbon credits trading", True),
        ("PFAS", "pfas restriction", True),
        ("VOC", "VOC limits", True),
        ("VOC", "VOCs are regulated", True),
        ("VOC", "vocational training", False),
        ("EPR", "EPRs in force", True),
        ("PM2.5", "PM2.5 limit", True),
    ],
)
def test_keyword_matching(keyword, text, expected):
    matcher = KeywordMatcher([keyword])

    assert bool(matcher.matches(text)) is expected


def test_prefix_requires_word_start():
    matcher = KeywordMatcher(["kar*"])

    assert matcher.matches("kara administracyjna") == ["kar*"]
    assert matcher.matches("prekaryjny") == []


def test_empty_keywords_are_ignored():
    assert compile_keyword("") is None
    assert compile_keyword("*") is None
    assert compile_keyword(None) is None
