class ActionClassifier:

    ACTION_PRIORITY = {

        "enacted_law": 100,
        "final_rule": 90,
        "proposed_rule": 80,
        "substance_update": 70,
        "scope_change": 60,
        "guidance": 50,
        "enforcement": 40,
        "postponement": 30,
        "amendment": 20
    }

    def __init__(self, taxonomy):

        self.rules = taxonomy["action_types"]

    def _match_keyword(
        self,
        keyword,
        text
    ):

        keyword = keyword.lower()

        if keyword.endswith("*"):
            return keyword[:-1] in text

        return keyword in text

    def classify(self, text):

        text = text.lower()

        matches = []

        for action, keywords in self.rules.items():

            for keyword in keywords:

                if self._match_keyword(
                    keyword,
                    text
                ):

                    matches.append(action)
                    break

        if not matches:
            return "unknown"

        matches.sort(
            key=lambda x:
            self.ACTION_PRIORITY.get(x, 0),
            reverse=True
        )

        return matches[0]
