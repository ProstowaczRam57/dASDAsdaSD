from regwatch.content_hash import content_hash
from regwatch.models import Publication


class StateManager:
    def __init__(self, db):
        self.db = db

    def get_hash(self, url: str):
        return self.db.get_hash(url)

    def save_publication(self, publication: Publication) -> None:
        if not publication.hash_value:
            publication.hash_value = content_hash(publication.content or "")

        self.db.save_publication(publication)

    def mark_seen(self, url: str) -> None:
        self.db.mark_seen(url)
