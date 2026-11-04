import logging
import os
from typing import Optional

import requests

logger = logging.getLogger("regwatch")

SYSTEM_PROMPT = (
    "You are a regulatory change analyst. You receive the previous and the "
    "current text of a monitored web page. Write a short summary of the "
    "substantive changes, in English, as 2-5 bullet points.\n\n"
    "Rules:\n"
    "- Focus on regulatory content: rules, requirements, deadlines, "
    "thresholds, substances, obligations, enforcement and legal status.\n"
    "- Ignore navigation, cookie notices, formatting, layout, and other "
    "boilerplate.\n"
    "- If the visible content is materially the same, reply exactly: "
    "'No substantive change.'\n"
    "- Do not repeat the full page text and do not add a preamble."
)


def truncate_middle(text: str, limit: int) -> str:
    """Keep the beginning and end of a long text within ``limit`` chars.

    Changes are often at the top or bottom of a page, so keeping both ends is
    more useful than cutting the text after N characters.
    """

    text = text or ""

    if limit <= 0 or len(text) <= limit:
        return text

    marker = "\n[... truncated ...]\n"
    head_size = max(1, (limit - len(marker)) // 2)
    tail_size = max(1, limit - len(marker) - head_size)

    return text[:head_size] + marker + text[-tail_size:]


class ChangeSummarizer:
    """Asks an OpenAI-compatible chat model to summarise page changes."""

    def __init__(self, settings: dict, session: Optional[requests.Session] = None):
        config = settings.get("ai") or {}

        self.enabled = bool(config.get("enabled", True))
        self.base_url = str(
            config.get("base_url", "https://api.openai.com/v1")
        ).rstrip("/")
        self.model = str(config.get("model", "gpt-4o-mini"))
        self.api_key_env = str(config.get("api_key_env", "OPENAI_API_KEY"))
        self.timeout_s = int(config.get("timeout_s", 90))
        self.max_body_chars = int(config.get("max_body_chars", 12000))
        self.max_output_tokens = int(config.get("max_output_tokens", 400))
        self.temperature = float(config.get("temperature", 0.2))

        self.api_key = (
            os.environ.get(self.api_key_env, "").strip()
            if self.api_key_env
            else ""
        )

        if self.enabled and not self.api_key:
            logger.warning(
                "AI summaries disabled: environment variable %s is not set",
                self.api_key_env,
            )
            self.enabled = False

        self.session = session or requests.Session()

    @property
    def requires_summary(self) -> bool:
        """When true, an old body may only be replaced after a summary."""

        return self.enabled

    def _build_user_prompt(
        self,
        old_body: str,
        new_body: str,
        title: str,
        url: str,
    ) -> str:
        old_text = truncate_middle(old_body, self.max_body_chars)
        new_text = truncate_middle(new_body, self.max_body_chars)

        return (
            f"Page title: {title}\n"
            f"URL: {url}\n\n"
            "=== PREVIOUS PAGE TEXT ===\n"
            f"{old_text}\n\n"
            "=== CURRENT PAGE TEXT ===\n"
            f"{new_text}\n"
        )

    def summarize(
        self,
        old_body: str,
        new_body: str,
        title: str,
        url: str,
    ) -> Optional[str]:
        if not self.enabled:
            return None

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": self._build_user_prompt(
                        old_body,
                        new_body,
                        title,
                        url,
                    ),
                },
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_output_tokens,
        }

        try:
            response = self.session.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.timeout_s,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
        except (
            requests.RequestException,
            ValueError,
            KeyError,
            IndexError,
            TypeError,
        ) as exc:
            logger.warning("AI summary failed for %s: %s", url, exc)
            return None

        summary = (content or "").strip()

        return summary or None

    def close(self) -> None:
        self.session.close()
