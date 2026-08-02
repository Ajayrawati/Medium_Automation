"""Collect, clean, de-duplicate, and store articles from configured sources."""

from __future__ import annotations

import argparse
from datetime import date
import logging
from pathlib import Path

import yaml
from dotenv import load_dotenv

from collectors.api.hackernews import HackerNewsCollector
from collectors.rss.collector import RSSCollector
from collectors.scraper.github_trending import GitHubTrendingCollector
from services.article_generator import GenerationError, generate_article
from services.cleaner import clean_article
from services.database import ArticleDatabase
from services.deduplicator import deduplicate
from services.exporter import export_evidence_audit, export_generated_article, export_topic_report
from services.research import collect_evidence
from services.topics import apply_manual_votes, cluster_topics, score_topics, select_topic

COLLECTORS = {
    "hackernews": HackerNewsCollector(),
    "github_trending": GitHubTrendingCollector(),
}


def load_sources(path: str | Path) -> dict:
    with Path(path).open(encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def _collect_articles(config: dict, limit: int) -> list:
    """Collect all configured sources without stopping on an individual source failure."""
    articles = []
    rss_collector = RSSCollector()

    for source in config.get("rss", []):
        try:
            articles.extend(rss_collector.collect(source, limit))
        except Exception as error:
            logging.warning("RSS source %s failed: %s", source.get("name", source.get("url")), error)

    for group in ("api", "scrapers"):
        for source in config.get(group, []):
            collector = COLLECTORS.get(source.get("type"))
            if collector is None:
                logging.warning("Unsupported collector type: %s", source.get("type"))
                continue
            try:
                articles.extend(collector.collect(source, limit))
            except Exception as error:
                logging.warning("Source %s failed: %s", source.get("name"), error)
    return deduplicate([clean_article(article) for article in articles if article.title and article.url])


def _parse_votes(votes: list[str]) -> dict[str, float]:
    parsed: dict[str, float] = {}
    for vote in votes:
        key, separator, value = vote.rpartition("=")
        if not separator or not key.strip():
            raise ValueError(f"Invalid vote {vote!r}; use TOPIC_KEY=NUMBER")
        parsed[key.strip().lower()] = float(value)
    return parsed


def run(
    config_path: str | Path,
    database_path: str | Path,
    limit: int,
    force: bool = False,
    manual_votes: dict[str, float] | None = None,
) -> int:
    """Run the full daily collection, selection, research, and generation workflow."""
    config = load_sources(config_path)
    settings = config.get("pipeline", {})
    article_settings = config.get("article", {})
    articles = _collect_articles(config, limit)

    votes = {str(key).lower(): float(value) for key, value in settings.get("manual_votes", {}).items()}
    votes.update(manual_votes or {})
    topics = apply_manual_votes(score_topics(cluster_topics(articles), settings), votes)
    today = date.today()
    output_dir = Path("output")
    with ArticleDatabase(database_path) as database:
        saved = sum(database.save(article) for article in articles)
        text_path = Path(database_path).with_suffix(".txt")
        database.export_text(text_path)
        topic_ids = {topic.key: database.upsert_topic(topic) for topic in topics}
        for topic in topics:
            topic_id = topic_ids[topic.key]
            database.save_vote(topic_id, "automatic", "system", topic.automatic_vote, "confidence plus corroboration")
            if topic.manual_vote:
                database.save_vote(topic_id, "manual", "config", topic.manual_vote, "manual_votes configuration")

        locked_key = database.get_selected_topic_key(today.isoformat())
        if locked_key and not force:
            selected = next((topic for topic in topics if topic.key == locked_key), None)
            if selected is None:
                logging.warning("Today's topic (%s) is locked but was not found in this collection; selection is unchanged.", locked_key)
                return saved
        else:
            selected = select_topic(
                topics,
                float(settings.get("confidence_threshold", 65)),
                int(settings.get("min_independent_sources", 2)),
            )
            if selected is not None:
                database.select_topic(topic_ids[selected.key], today.isoformat(), selected.final_vote)

        if selected is None:
            logging.info("Collected %d unique articles; saved %d new articles. No topic met the confidence threshold.", len(articles), saved)
            return saved

        export_topic_report(selected, output_dir / f"{today.isoformat()}-topic.md")
        evidence = collect_evidence(
            selected,
            int(settings.get("research_passes", 2)),
            int(settings.get("max_evidence_per_topic", 6)),
        )
        database.save_evidence(topic_ids[selected.key], evidence)
        export_evidence_audit(selected, evidence, output_dir / f"{today.isoformat()}-evidence.json")
        if len(evidence) < int(settings.get("min_evidence_sources", 2)):
            logging.warning("Selected topic %s has only %d verified evidence sources; article generation skipped.", selected.title, len(evidence))
            return saved
        try:
            generated = generate_article(selected, evidence, article_settings, today)
        except GenerationError as error:
            logging.warning("Article generation skipped: %s", error)
            return saved
        database.save_generated_article(topic_ids[selected.key], generated)
        export_generated_article(generated, output_dir / f"{today.isoformat()}-article.md")

    logging.info("Collected %d unique articles; saved %d new articles; generated an article for %s.", len(articles), saved, selected.title)
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect configured news and repository articles.")
    parser.add_argument("--config", default="config/sources.yaml", help="Path to the source configuration file.")
    parser.add_argument("--database", default="storage/articles.db", help="Path to the SQLite database.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum articles per source.")
    parser.add_argument("--force", action="store_true", help="Replace today's locked topic selection.")
    parser.add_argument("--vote", action="append", default=[], metavar="TOPIC_KEY=NUMBER", help="Apply a manual vote adjustment; can be passed more than once.")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    load_dotenv()
    try:
        manual_votes = _parse_votes(args.vote)
    except ValueError as error:
        parser.error(str(error))
    run(args.config, args.database, args.limit, args.force, manual_votes)


if __name__ == "__main__":
    main()
