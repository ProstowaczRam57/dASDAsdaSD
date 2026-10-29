import pytest
import requests
from regwatch.fetcher import Fetcher, FetchError, fetcher_from_settings


class FakeResponse:
    def __init__(self, text="<html></html>", status=200, content_type="text/html"):
        self.text = text
        self.status_code = status
        self.headers = {"Content-Type": content_type} if content_type else {}
        self.encoding = "utf-8"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.headers = {}
        self.kwargs = []

    def get(self, url, **kwargs):
        self.kwargs.append(kwargs)
        return self.response

    def mount(self, prefix, adapter):
        pass

    def close(self):
        self.closed = True


def test_rejects_non_http_urls():
    fetcher = Fetcher(session=FakeSession(FakeResponse()))

    for url in ("ftp://example.com/x", "file:///etc/passwd", "example.com"):
        with pytest.raises(FetchError, match="Unsupported URL scheme|no host"):
            fetcher.get(url)


def test_returns_html():
    session = FakeSession(FakeResponse("<html>ok</html>"))
    fetcher = Fetcher(session=session, timeout=5, verify_ssl=False)

    assert fetcher.get("https://example.com") == "<html>ok</html>"
    assert session.kwargs[0]["timeout"] == 5
    assert session.kwargs[0]["verify"] is False


def test_http_errors_become_fetch_errors():
    fetcher = Fetcher(session=FakeSession(FakeResponse(status=404)))

    with pytest.raises(FetchError, match="HTTP 404"):
        fetcher.get("https://example.com/missing")


def test_unsupported_content_type_is_rejected():
    fetcher = Fetcher(
        session=FakeSession(
            FakeResponse(content_type="application/octet-stream")
        )
    )

    with pytest.raises(FetchError, match="Unsupported content type"):
        fetcher.get("https://example.com/blob")


def test_fetcher_from_settings_reads_crawler_section():
    settings = {
        "crawler": {
            "timeout_s": 7,
            "max_retries": 2,
            "verify_ssl": False,
            "user_agent": "TestAgent/2.0",
        }
    }

    fetcher = fetcher_from_settings(settings, request_delay_s=1.5)

    assert fetcher.timeout == 7
    assert fetcher.verify_ssl is False
    assert fetcher.request_delay_s == 1.5
    assert fetcher.session.headers["User-Agent"] == "TestAgent/2.0"
