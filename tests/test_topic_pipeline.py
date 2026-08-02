from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from models.article import Article
from services.database import ArticleDatabase
from services.exporter import export_generated_article
from services.topics import apply_manual_votes, cluster_topics, score_topics, select_topic
from models.topic import Evidence, GeneratedArticle


SETTINGS = {
    "min_independent_sources": 2,
    "category_weights": {"technology": 1.0},
    "confidence_weights": {
        "source_quality": 0.30,
        "corroboration": 0.25,
        "recency": 0.20,
        "relevance": 0.15,
        "momentum": 0.10,
    },
}


class TopicPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        timestamp = datetime.now(timezone.utc)
        self.articles = [
            Article("Acme AI tool launches", "https://example.com/acme-ai", "Source A", "technology", "Acme AI tool launch", timestamp, metadata={"publisher": "example.com", "source_reliability": 0.9}),
            Article("Acme AI tool reaches users", "https://news.example.org/acme-ai", "Source B", "technology", "Acme AI tool reaches users", timestamp, metadata={"publisher": "news.example.org", "source_reliability": 0.8}),
        ]

    def test_related_articles_are_scored_and_selected(self) -> None:
        topics = apply_manual_votes(score_topics(cluster_topics(self.articles), SETTINGS), {})
        selected = select_topic(topics, minimum_confidence=65, minimum_sources=2)
        self.assertIsNotNone(selected)
        self.assertGreaterEqual(selected.confidence, 65)

    def test_database_persists_daily_selection(self) -> None:
        topic = score_topics(cluster_topics(self.articles), SETTINGS)[0]
        with TemporaryDirectory() as directory:
            with ArticleDatabase(Path(directory) / "articles.db") as database:
                topic_id = database.upsert_topic(topic)
                database.select_topic(topic_id, "2026-08-02", topic.final_vote)
                self.assertEqual(database.get_selected_topic_key("2026-08-02"), topic.key)

    def test_medium_export_uses_placeholder_and_verified_code_only(self) -> None:
        evidence = Evidence(
            article_url="https://example.com/code",
            source="Source A",
            publisher="example.com",
            title="Example implementation",
            excerpt="A verified excerpt.",
            reliability=0.9,
            collected_at=datetime.now(timezone.utc),
            code_snippet="print('verified')",
        )
        article = GeneratedArticle(
            topic_key="acme-ai",
            title="Acme AI",
            body="*A concise subtitle.*\n\n## Key takeaways\n\n- Verified point.",
            confidence=90,
            generated_for=date(2026, 8, 2),
            sources=[evidence],
            generator="gemini-3.5-flash-lite",
        )
        with TemporaryDirectory() as directory:
            output = Path(directory) / "article.md"
            export_generated_article(article, output)
            content = output.read_text(encoding="utf-8")
        self.assertIn("Cover visual", content)
        self.assertIn("## Verified code example", content)
        self.assertIn("print('verified')", content)


if __name__ == "__main__":
    unittest.main()
