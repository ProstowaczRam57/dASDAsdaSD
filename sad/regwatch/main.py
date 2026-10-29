import argparse
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence

from regwatch import __version__
from regwatch.action_classifier import ActionClassifier
from regwatch.config_loader import ConfigError, ConfigLoader
from regwatch.date_filter import DateFilter
from regwatch.db import Database
from regwatch.fetcher import Fetcher, FetchError, fetcher_from_settings
from regwatch.html_parser import HtmlParser
from regwatch.link_discovery import discover_links
from regwatch.models import Publication, Source
from regwatch.paths import PROJECT_ROOT, resolve_path
from regwatch.publication_detector import PublicationDetector
from regwatch.report_generator import ReportGenerator
from regwatch.scoring import ImpactScorer
from regwatch.state_manager import StateManager
from regwatch.taxonomy_matcher import TaxonomyMatcher

DEFAULT_MAX_LINKS = 50
LOG_FORMAT = "%(asctime)s %(levelname)-7s %(message)s"

logger = logging.getLogger("regwatch")


@dataclass
class RunStats:
    sources_scanned: int = 0
    links_seen: int = 0
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped_old: int = 0
    errors: int = 0
    reports: List[Path] = field(default_factory=list)

    def as_dict(self) -> dict:
        data = {
            "sources_scanned": self.sources_scanned,
            "links_seen": self.links_seen,
            "new": self.new,
            "updated": self.updated,
            "unchanged": self.unchanged,
            "skipped_old": self.skipped_old,
            "errors": self.errors,
        }
        data["reports"] = [str(path) for path in self.reports]

        return data


def configure_logging(
    settings: dict,
    base_dir: Path,
    verbose: bool = False,
) -> None:
    logging_settings = settings.get("logging") or {}
    level_name = str(logging_settings.get("level", "INFO")).upper()
    level = getattr(logging, level_name, logging.INFO)

    if verbose:
        level = logging.DEBUG

    handlers: List[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    log_file = logging_settings.get("file")

    if log_file:
        log_path = resolve_path(str(log_file), base_dir)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True,
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="regwatch",
        description="Monitor regulatory sources and store new publications.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--config-dir",
        help="Directory with settings.yaml, sources.yaml and taxonomy.yaml",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        help="Override monitoring.lookback_days",
    )
    parser.add_argument(
        "--max-links",
        type=int,
        help=(
            "Maximum links followed per source "
            f"(default {DEFAULT_MAX_LINKS}; 0 = unlimited)"
        ),
    )
    parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        metavar="ID",
        help="Only scan this source id (repeatable)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and classify without writing to the database",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Do not generate HTML/CSV reports",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging and tracebacks",
    )
    return parser.parse_args(argv)


def _warn_unsupported_type(source: Source) -> None:
    logger.warning(
        "Source %s has type '%s'; only 'page' is implemented, skipping",
        source.id,
        source.type,
    )


def _resolve_max_links(
    requested: Optional[int],
    tracking: dict,
) -> Optional[int]:
    value = requested

    if value is None:
        value = tracking.get("max_subpages")

    if value is None:
        value = DEFAULT_MAX_LINKS

    value = int(value)

    return None if value == 0 else value


def _process_source(
    source: Source,
    *,
    fetcher: Fetcher,
    parser: HtmlParser,
    state: StateManager,
    detector: PublicationDetector,
    matcher: TaxonomyMatcher,
    action_classifier: ActionClassifier,
    scorer: ImpactScorer,
    date_filter: DateFilter,
    max_links: Optional[int],
    detect_flags: dict,
    dry_run: bool,
    stats: RunStats,
) -> None:
    source_html = fetcher.get(source.url)
    links = discover_links(source_html, source.url, max_links=max_links)

    if not links:
        logger.debug("No links found on %s, scanning the page itself", source.id)
        links = [source.url]

    logger.info("Scanning %s (%d links)", source.name, len(links))

    for link in links:
        stats.links_seen += 1

        try:
            html = fetcher.get(link)
            title = parser.extract_title(html)
            content = parser.extract_text(html)
            publication_date = parser.extract_date(html)

            if not content.strip():
                logger.debug("Empty content, skipping %s", link)
                continue

            if not date_filter.is_recent(publication_date):
                stats.skipped_old += 1
                logger.debug("Old publication, skipping %s", link)
                continue

            previous_hash = state.get_hash(link)
            change = detector.detect(content, previous_hash)

            if change == "UNCHANGED":
                stats.unchanged += 1

                if not dry_run:
                    state.mark_seen(link)

                continue

            domain, topic = matcher.classify(content)
            action_type = action_classifier.classify(content)

            publication = Publication(
                source_id=source.id,
                source_name=source.name,
                title=title,
                url=link,
                content=content,
                published_date=publication_date,
                domain=domain or "",
                topic=topic or "",
                action_type=action_type,
                change_type=change,
            )
            publication.impact_score = scorer.score(publication, change)

            if change == "NEW" and not detect_flags.get(
                "new_publications", True
            ):
                logger.debug("New publication detection disabled, skipping")
                continue

            if change == "UPDATED" and not detect_flags.get(
                "modified_publications", True
            ):
                logger.debug("Modified publication detection disabled, skipping")
                continue

            if change == "NEW":
                stats.new += 1
            else:
                stats.updated += 1

            if dry_run:
                logger.info(
                    "[dry-run] [%s] %s | %s | %s",
                    change,
                    domain,
                    topic,
                    action_type,
                )
            else:
                state.save_publication(publication)

                logger.info(
                    "[%s] %s | %s | %s | score=%d",
                    change,
                    domain,
                    topic,
                    action_type,
                    publication.impact_score,
                )

            logger.debug("    %s", title)

        except (FetchError, ValueError) as exc:
            stats.errors += 1
            logger.warning("Failed link %s: %s", link, exc)
        except Exception as exc:  # keep a bad page from aborting the source
            stats.errors += 1
            logger.warning("Unexpected error for %s: %s", link, exc)
            logger.debug("Traceback for %s", link, exc_info=True)


def run(
    config_dir: Optional[str] = None,
    lookback_days: Optional[int] = None,
    max_links: Optional[int] = None,
    source_ids: Optional[Sequence[str]] = None,
    dry_run: bool = False,
    generate_report: bool = True,
    verbose: bool = False,
    fetcher: Optional[Fetcher] = None,
) -> RunStats:
    loader = ConfigLoader(config_dir)
    settings = loader.load_settings()
    base_dir = (
        Path(config_dir).expanduser().resolve().parent
        if config_dir
        else PROJECT_ROOT
    )

    configure_logging(settings, base_dir, verbose=verbose)

    sources = loader.load_sources()
    taxonomy = loader.load_taxonomy()
    runtime = loader.load_runtime_options()

    database_path = resolve_path(settings["database"]["path"], base_dir)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    for key in ("snapshots_dir", "cache_dir", "reports_dir"):
        value = (settings.get("storage") or {}).get(key)

        if value:
            resolve_path(str(value), base_dir).mkdir(parents=True, exist_ok=True)

    if lookback_days is None:
        lookback_days = int(
            (settings.get("monitoring") or {}).get("lookback_days", 30)
        )

    detect_flags = (settings.get("monitoring") or {}).get("detect") or {}
    tracking = runtime.get("default_tracking") or {}
    effective_max_links = _resolve_max_links(max_links, tracking)

    if detect_flags.get("removed_publications"):
        logger.warning(
            "monitoring.detect.removed_publications is enabled but removal "
            "detection is not implemented; ignoring"
        )

    compare_mode = str(tracking.get("compare_mode", "content_hash")).lower()

    if compare_mode != "content_hash":
        logger.warning(
            "compare_mode '%s' is not supported, using content_hash",
            compare_mode,
        )

    parser = HtmlParser()
    matcher = TaxonomyMatcher(taxonomy)
    action_classifier = ActionClassifier(taxonomy)
    detector = PublicationDetector()
    scorer = ImpactScorer(settings)
    date_filter = DateFilter(lookback_days)

    owned_fetcher = fetcher is None
    client = fetcher or fetcher_from_settings(
        settings,
        request_delay_s=runtime.get("request_delay_s", 0.0),
    )

    stats = RunStats()
    db: Optional[Database] = None
    state: Optional[StateManager] = None
    run_id = None

    selected_ids = set(source_ids or [])

    try:
        db = Database(str(database_path))
        state = StateManager(db)

        if not dry_run:
            run_id = db.start_run()

        for source in sources:
            if not source.enabled:
                continue

            if selected_ids and source.id not in selected_ids:
                continue

            if source.type != "page":
                _warn_unsupported_type(source)
                continue

            stats.sources_scanned += 1

            try:
                _process_source(
                    source,
                    fetcher=client,
                    parser=parser,
                    state=state,
                    detector=detector,
                    matcher=matcher,
                    action_classifier=action_classifier,
                    scorer=scorer,
                    date_filter=date_filter,
                    max_links=effective_max_links,
                    detect_flags=detect_flags,
                    dry_run=dry_run,
                    stats=stats,
                )
            except (FetchError, ValueError) as exc:
                stats.errors += 1
                logger.error("Failed source %s: %s", source.name, exc)
            except Exception as exc:
                stats.errors += 1
                logger.error("Unexpected error for source %s: %s", source.name, exc)
                logger.debug("Traceback for source %s", source.id, exc_info=True)

        if generate_report and not dry_run:
            reports_dir = resolve_path(
                str((settings.get("storage") or {}).get("reports_dir", "data/reports")),
                base_dir,
            )
            stats.reports = ReportGenerator(settings, reports_dir).generate(
                db.recent_publications(lookback_days)
            )

        if selected_ids and stats.sources_scanned == 0:
            logger.warning(
                "No enabled sources matched: %s",
                ", ".join(sorted(selected_ids)),
            )

    finally:
        if db is not None:
            if run_id is not None:
                db.finish_run(run_id, stats.new + stats.updated)

            db.close()

        if owned_fetcher:
            client.close()

    logger.info(
        "Done: %d sources, %d links, %d new, %d updated, %d unchanged, "
        "%d skipped, %d errors",
        stats.sources_scanned,
        stats.links_seen,
        stats.new,
        stats.updated,
        stats.unchanged,
        stats.skipped_old,
        stats.errors,
    )

    if generate_report and not dry_run:
        for report in stats.reports:
            logger.info("Report written: %s", report)

    return stats


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    try:
        stats = run(
            config_dir=args.config_dir,
            lookback_days=args.lookback_days,
            max_links=args.max_links,
            source_ids=args.sources,
            dry_run=args.dry_run,
            generate_report=not args.no_report,
            verbose=args.verbose,
        )
    except ConfigError as exc:
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

        logger.error("Configuration error: %s", exc)
        return 2
    except KeyboardInterrupt:
        logger.warning("Interrupted")
        return 130
    except Exception as exc:
        if not logging.getLogger().handlers:
            logging.basicConfig(level=logging.INFO)

        logger.error("Fatal error: %s", exc)
        logger.debug("Traceback", exc_info=True)
        return 1

    return 0 if stats.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
