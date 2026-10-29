from regwatch.config_loader import ConfigLoader

from regwatch.fetcher import Fetcher
from regwatch.link_discovery import discover_links

from regwatch.html_parser import HtmlParser
from regwatch.date_filter import DateFilter

from regwatch.taxonomy_matcher import TaxonomyMatcher
from regwatch.action_classifier import ActionClassifier

from regwatch.publication_detector import PublicationDetector

from regwatch.db import Database
from regwatch.state_manager import StateManager


def main():

    # ==============================
    # LOAD CONFIGURATION
    # ==============================

    settings = ConfigLoader.load_settings()

    sources_config = ConfigLoader.load_sources()

    taxonomy = ConfigLoader.load_taxonomy()

    # ==============================
    # INITIALIZE SERVICES
    # ==============================

    parser = HtmlParser()

    matcher = TaxonomyMatcher(
        taxonomy
    )

    action_classifier = ActionClassifier(
        taxonomy
    )

    fetcher = Fetcher(
        timeout=settings["crawler"]["timeout_s"]
    )

    detector = PublicationDetector()

    db = Database(
        settings["database"]["path"]
    )

    state = StateManager(
        db
    )

    lookback_days = settings[
        "monitoring"
    ]["lookback_days"]

    # ==============================
    # PROCESS SOURCES
    # ==============================

    for source in sources_config["sources"]:

        if not source.get(
            "enabled",
            True
        ):
            continue

        print(
            f"\nScanning: {source['name']}"
        )

        try:

            source_html = fetcher.get(
                source["url"]
            )

            links = discover_links(
                source_html,
                source["url"]
            )

            # fallback
            if not links:
                links = [source["url"]]

            print(
                f"Found {len(links)} links"
            )

            for link in links:

                try:

                    html = fetcher.get(
                        link
                    )

                    title = parser.extract_title(
                        html
                    )

                    content = parser.extract_text(
                        html
                    )

                    publication_date = (
                        parser.extract_date(
                            html
                        )
                    )

                    # --------------------------
                    # SKIP OLD PUBLICATIONS
                    # --------------------------

                    if not DateFilter.is_recent(
                        publication_date,
                        lookback_days
                    ):

                        print(
                            f"Skipping old publication: "
                            f"{title}"
                        )

                        continue

                    # --------------------------
                    # CHANGE DETECTION
                    # --------------------------

                    old_hash = state.get_hash(
                        link
                    )

                    change = detector.detect(
                        content,
                        old_hash
                    )

                    if change == "UNCHANGED":
                        continue

                    # --------------------------
                    # CLASSIFICATION
                    # --------------------------

                    domain, topic = (
                        matcher.classify(
                            content
                        )
                    )

                    action_type = (
                        action_classifier.classify(
                            content
                        )
                    )

                    # --------------------------
                    # SAVE
                    # --------------------------

                    publication = {

                        "source_id":
                            source["id"],

                        "title":
                            title,

                        "url":
                            link,

                        "content":
                            content,

                        "published_date":
                            (
                                publication_date.isoformat()
                                if publication_date
                                else None
                            ),

                        "domain":
                            domain,

                        "topic":
                            topic,

                        "action_type":
                            action_type,

                        "impact_score":
                            0
                    }

                    state.save_publication(
                        publication
                    )

                    print(
                        f"[{change}] "
                        f"{topic} | "
                        f"{action_type}"
                    )

                    print(
                        f"    {title}"
                    )

                except Exception as exc:

                    print(
                        f"Failed link:"
                    )

                    print(link)

                    print(exc)

        except Exception as exc:

            print(
                f"Failed source:"
            )

            print(
                source["name"]
            )

            print(exc)


if __name__ == "__main__":
    main()



