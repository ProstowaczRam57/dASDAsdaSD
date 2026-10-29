import time
from typing import Optional
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_USER_AGENT = "RegulatoryMonitor/1.0 (+https://company.internal)"


class FetchError(RuntimeError):
    """Raised when a page cannot be fetched or is not HTML."""


class Fetcher:
    """HTTP client with retries, timeouts and polite per-host throttling."""

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        user_agent: str = DEFAULT_USER_AGENT,
        verify_ssl: bool = True,
        request_delay_s: float = 0.0,
        session: Optional[requests.Session] = None,
    ):
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.request_delay_s = max(0.0, request_delay_s)
        self.user_agent = (user_agent or DEFAULT_USER_AGENT).strip()
        self._last_request_at = 0.0

        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en;q=0.9",
            }
        )

        retry = Retry(
            total=max_retries,
            connect=max_retries,
            read=max_retries,
            status=max_retries,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "HEAD"}),
            raise_on_status=False,
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _throttle(self) -> None:
        if not self.request_delay_s:
            return

        elapsed = time.monotonic() - self._last_request_at

        if elapsed < self.request_delay_s:
            time.sleep(self.request_delay_s - elapsed)

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)

        if parsed.scheme not in {"http", "https"}:
            raise FetchError(f"Unsupported URL scheme: {url}")

        if not parsed.netloc:
            raise FetchError(f"URL has no host: {url}")

    def get(self, url: str) -> str:
        self._validate_url(url)
        self._throttle()

        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                verify=self.verify_ssl,
                allow_redirects=True,
            )
        except requests.RequestException as exc:
            raise FetchError(f"Request failed for {url}: {exc}") from exc
        finally:
            self._last_request_at = time.monotonic()

        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise FetchError(
                f"HTTP {response.status_code} for {url}"
            ) from exc

        content_type = (response.headers.get("Content-Type") or "").lower()

        if "pdf" in content_type:
            raise FetchError(f"Skipping PDF document: {url}")

        if content_type and not any(
            marker in content_type
            for marker in ("html", "xml", "text/plain")
        ):
            raise FetchError(
                f"Unsupported content type '{content_type}' for {url}"
            )

        if response.encoding is None:
            response.encoding = response.apparent_encoding or "utf-8"

        return response.text

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "Fetcher":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()


def fetcher_from_settings(
    settings: dict,
    request_delay_s: float = 0.0,
) -> Fetcher:
    crawler = settings.get("crawler", {})

    return Fetcher(
        timeout=int(crawler.get("timeout_s", 30)),
        max_retries=int(crawler.get("max_retries", 3)),
        user_agent=str(crawler.get("user_agent", DEFAULT_USER_AGENT)),
        verify_ssl=bool(crawler.get("verify_ssl", True)),
        request_delay_s=request_delay_s,
    )
