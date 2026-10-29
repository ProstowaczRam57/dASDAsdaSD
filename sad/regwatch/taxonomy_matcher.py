import re


class TaxonomyMatcher:

    def __init__(self, taxonomy):

        self.taxonomy = taxonomy

    def classify(self, text):

        text = text.lower()

        best_score = 0

        best_domain = None
        best_topic = None

        for domain, topics in self.taxonomy["domains"].items():

            for topic, keywords in topics.items():

                score = 0

                for keyword in keywords:

                    keyword = keyword.lower()

                    if keyword.replace("*", "") in text:
                        score += 1

                if score > best_score:

                    best_score = score

                    best_domain = domain

                    best_topic = topic

        return best_domain, best_topic
