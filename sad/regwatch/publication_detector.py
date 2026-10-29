from regwatch.content_hash import content_hash


class PublicationDetector:

    def detect(
        self,
        content,
        previous_hash
    ):

        current_hash = content_hash(content)

        if previous_hash is None:
            return "NEW"

        if current_hash != previous_hash:
            return "UPDATED"

        return "UNCHANGED"

