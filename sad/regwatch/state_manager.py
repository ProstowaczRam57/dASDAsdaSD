from regwatch.content_hash import content_hash



class StateManager:

    def __init__(self, db):
        self.db = db

    def get_hash(self, url):

        return self.db.get_hash(
            url
        )

    def save_publication(
        self,
        publication
    ):

        publication["hash_value"] = (
            content_hash(
                publication["content"]
            )
        )

        self.db.save_publication(
            publication
        )
