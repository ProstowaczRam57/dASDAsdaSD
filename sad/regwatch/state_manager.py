from regwatch.content_hash import content_hash
from regwatch.models import Publication


class StateManager:
    def __init__(self, db):
        self.db = db

    def get_state(self, url: str):
        return self.db.get_state(url)

    def get_hash(self, url: str):
        return self.db.get_hash(url)

    def save_publication(self, publication: Publication) -> None:
        if not publication.content_hash:
            publication.content_hash = content_hash(publication.body or "")

        self.db.save_publication(publication)

    def mark_seen(self, url: str) -> None:
        self.db.mark_seen(url)
