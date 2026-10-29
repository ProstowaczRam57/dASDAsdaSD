from typing import Optional

from regwatch.content_hash import content_hash


class PublicationDetector:
    """Compares the stored hash with the freshly extracted content."""

    def detect(self, content: str, previous_hash: Optional[str]) -> str:
        current_hash = content_hash(content or "")

        if previous_hash is None:
            return "NEW"

        if current_hash != previous_hash:
            return "UPDATED"

        return "UNCHANGED"
