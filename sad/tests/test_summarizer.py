import requests

from regwatch.summarizer import ChangeSummarizer, truncate_middle

SETTINGS = {
    "ai": {
        "enabled": True,
        "base_url": "https://api.example.test/v1/",
        "model": "test-model",
        "api_key_env": "TEST_AI_KEY",
        "timeout_s": 5,
        "max_body_chars": 500,
        "max_output_tokens": 120,
        "temperature": 0.1,
    }
}

OLD = "Old rule: limit is 10 ppm. " * 50
NEW = "New rule: limit is 5 ppm. " * 50


class FakeResponse:
    def __init__(self, content="- Limit changed from 10 to 5 ppm.", status=200):
        self.content = content
        self.status = status

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(f"{self.status}")

    def json(self):
        return {"choices": [{"message": {"content": self.content}}]}


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []
        self.closed = False

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.response

    def close(self):
        self.closed = True


def test_missing_api_key_disables_summaries(monkeypatch):
    monkeypatch.delenv("TEST_AI_KEY", raising=False)
    session = FakeSession(FakeResponse())

    summarizer = ChangeSummarizer(SETTINGS, session=session)

    assert summarizer.enabled is False
    assert summarizer.requires_summary is False
    assert summarizer.summarize("old", "new", "t", "u") is None
    assert session.calls == []


def test_disabled_in_settings(monkeypatch):
    monkeypatch.setenv("TEST_AI_KEY", "secret")
    settings = {"ai": dict(SETTINGS["ai"], enabled=False)}

    summarizer = ChangeSummarizer(settings, session=FakeSession(FakeResponse()))

    assert summarizer.enabled is False
    assert summarizer.requires_summary is False


def test_summary_is_requested_with_both_bodies(monkeypatch):
    monkeypatch.setenv("TEST_AI_KEY", "secret")
    session = FakeSession(FakeResponse())
    summarizer = ChangeSummarizer(SETTINGS, session=session)

    summary = summarizer.summarize(OLD, NEW, "PFAS rule", "https://example.com")

    assert summary == "- Limit changed from 10 to 5 ppm."

    url, kwargs = session.calls[0]
    assert url == "https://api.example.test/v1/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer secret"
    assert kwargs["json"]["model"] == "test-model"
    assert kwargs["json"]["max_tokens"] == 120

    prompt = kwargs["json"]["messages"][1]["content"]
    assert "PREVIOUS PAGE TEXT" in prompt
    assert "CURRENT PAGE TEXT" in prompt
    assert "limit is 10 ppm" in prompt
    assert "limit is 5 ppm" in prompt
    # Bodies longer than max_body_chars are shortened for the model.
    assert len(prompt) < 2 * 500 + 500


def test_failed_request_returns_none(monkeypatch):
    monkeypatch.setenv("TEST_AI_KEY", "secret")
    summarizer = ChangeSummarizer(
        SETTINGS,
        session=FakeSession(FakeResponse(status=500)),
    )

    assert summarizer.requires_summary is True
    assert summarizer.summarize("old", "new", "t", "u") is None


def test_empty_model_response_returns_none(monkeypatch):
    monkeypatch.setenv("TEST_AI_KEY", "secret")
    summarizer = ChangeSummarizer(
        SETTINGS,
        session=FakeSession(FakeResponse(content="   ")),
    )

    assert summarizer.summarize("old", "new", "t", "u") is None


def test_truncate_middle_keeps_head_and_tail():
    text = "A" * 100 + "MIDDLE" + "B" * 100

    result = truncate_middle(text, 60)

    assert len(result) <= 60
    assert result.startswith("A")
    assert result.endswith("B")
    assert "truncated" in result


def test_truncate_middle_short_text_is_untouched():
    assert truncate_middle("short", 100) == "short"
