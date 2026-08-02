"""SQLite persistence for collected articles."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from models.article import Article
from models.topic import Evidence, GeneratedArticle, Topic
from services.deduplicator import canonical_url


class ArticleDatabase:
    def __init__(self, path: str | Path = "storage/articles.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self) -> None:
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                source TEXT NOT NULL,
                category TEXT NOT NULL,
                summary TEXT NOT NULL DEFAULT '',
                published_at TEXT,
                score INTEGER,
                metadata TEXT NOT NULL DEFAULT '{}',
                collected_at TEXT NOT NULL
            )
            """
        )
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY,
                topic_key TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                confidence REAL NOT NULL,
                score_breakdown TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS topic_selections (
                id INTEGER PRIMARY KEY,
                topic_id INTEGER NOT NULL REFERENCES topics(id),
                selected_for TEXT NOT NULL UNIQUE,
                final_vote REAL NOT NULL,
                status TEXT NOT NULL,
                selected_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS topic_votes (
                id INTEGER PRIMARY KEY,
                topic_id INTEGER NOT NULL REFERENCES topics(id),
                vote_type TEXT NOT NULL,
                voter TEXT NOT NULL,
                value REAL NOT NULL,
                rationale TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS evidence (
                id INTEGER PRIMARY KEY,
                topic_id INTEGER NOT NULL REFERENCES topics(id),
                article_url TEXT NOT NULL,
                source TEXT NOT NULL,
                publisher TEXT NOT NULL,
                title TEXT NOT NULL,
                excerpt TEXT NOT NULL,
                reliability REAL NOT NULL,
                corroborated INTEGER NOT NULL,
                retrieval_status TEXT NOT NULL,
                collected_at TEXT NOT NULL,
                UNIQUE(topic_id, article_url)
            );
            CREATE TABLE IF NOT EXISTS generated_articles (
                id INTEGER PRIMARY KEY,
                topic_id INTEGER NOT NULL REFERENCES topics(id),
                generated_for TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                confidence REAL NOT NULL,
                generator TEXT NOT NULL,
                sources TEXT NOT NULL,
                generated_at TEXT NOT NULL
            );
            """
        )
        self._add_column_if_missing("evidence", "code_snippet", "TEXT NOT NULL DEFAULT ''")
        self.connection.commit()

    def _add_column_if_missing(self, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in self.connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def save(self, article: Article) -> bool:
        """Persist an article, returning True only when it is new."""
        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO articles
            (title, url, source, category, summary, published_at, score, metadata, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                article.title, canonical_url(article.url), article.source, article.category,
                article.summary, article.published_at.isoformat() if article.published_at else None,
                article.score, json.dumps(article.metadata), datetime.now().astimezone().isoformat(),
            ),
        )
        self.connection.commit()
        return cursor.rowcount == 1

    def export_text(self, path: str | Path) -> None:
        """Write all saved articles to a readable plain-text file."""
        rows = self.connection.execute(
            """
            SELECT title, source, category, url, summary, published_at, score
            FROM articles
            ORDER BY id DESC
            """
        ).fetchall()
        blocks = []
        for row in rows:
            details = [
                row["title"],
                f"Source: {row['source']}",
                f"Category: {row['category']}",
                f"URL: {row['url']}",
            ]
            if row["published_at"]:
                details.append(f"Published: {row['published_at']}")
            if row["score"] is not None:
                details.append(f"Score: {row['score']}")
            if row["summary"]:
                details.extend(("", row["summary"]))
            blocks.append("\n".join(details))

        output = Path(path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n\n".join(blocks) + ("\n" if blocks else ""), encoding="utf-8")

    def upsert_topic(self, topic: Topic) -> int:
        now = datetime.now().astimezone().isoformat()
        self.connection.execute(
            """
            INSERT INTO topics (topic_key, title, category, confidence, score_breakdown, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(topic_key) DO UPDATE SET
                title=excluded.title, category=excluded.category, confidence=excluded.confidence,
                score_breakdown=excluded.score_breakdown, updated_at=excluded.updated_at
            """,
            (topic.key, topic.title, topic.category, topic.confidence, json.dumps(topic.score_breakdown), now),
        )
        row = self.connection.execute("SELECT id FROM topics WHERE topic_key = ?", (topic.key,)).fetchone()
        self.connection.commit()
        return int(row["id"])

    def get_selected_topic_key(self, selected_for: str) -> str | None:
        row = self.connection.execute(
            """SELECT topics.topic_key FROM topic_selections
               JOIN topics ON topics.id = topic_selections.topic_id
               WHERE selected_for = ?""",
            (selected_for,),
        ).fetchone()
        return str(row["topic_key"]) if row else None

    def select_topic(self, topic_id: int, selected_for: str, final_vote: float) -> None:
        self.connection.execute(
            """
            INSERT INTO topic_selections (topic_id, selected_for, final_vote, status, selected_at)
            VALUES (?, ?, ?, 'selected', ?)
            ON CONFLICT(selected_for) DO UPDATE SET
                topic_id=excluded.topic_id, final_vote=excluded.final_vote, status='selected', selected_at=excluded.selected_at
            """,
            (topic_id, selected_for, final_vote, datetime.now().astimezone().isoformat()),
        )
        self.connection.commit()

    def save_vote(self, topic_id: int, vote_type: str, voter: str, value: float, rationale: str) -> None:
        self.connection.execute(
            """INSERT INTO topic_votes (topic_id, vote_type, voter, value, rationale, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (topic_id, vote_type, voter, value, rationale, datetime.now().astimezone().isoformat()),
        )
        self.connection.commit()

    def save_evidence(self, topic_id: int, evidence_items: list[Evidence]) -> None:
        self.connection.executemany(
            """
            INSERT INTO evidence
            (topic_id, article_url, source, publisher, title, excerpt, reliability, corroborated, retrieval_status, code_snippet, collected_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(topic_id, article_url) DO UPDATE SET
                excerpt=excluded.excerpt, reliability=excluded.reliability, corroborated=excluded.corroborated,
                retrieval_status=excluded.retrieval_status, code_snippet=excluded.code_snippet, collected_at=excluded.collected_at
            """,
            [
                (topic_id, item.article_url, item.source, item.publisher, item.title, item.excerpt,
                 item.reliability, int(item.corroborated), item.retrieval_status, item.code_snippet, item.collected_at.isoformat())
                for item in evidence_items
            ],
        )
        self.connection.commit()

    def save_generated_article(self, topic_id: int, article: GeneratedArticle) -> None:
        sources = [
            {"title": item.title, "publisher": item.publisher, "url": item.article_url}
            for item in article.sources
        ]
        self.connection.execute(
            """
            INSERT INTO generated_articles
            (topic_id, generated_for, title, body, confidence, generator, sources, generated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(generated_for) DO UPDATE SET
                topic_id=excluded.topic_id, title=excluded.title, body=excluded.body, confidence=excluded.confidence,
                generator=excluded.generator, sources=excluded.sources, generated_at=excluded.generated_at
            """,
            (topic_id, article.generated_for.isoformat(), article.title, article.body, article.confidence,
             article.generator, json.dumps(sources), datetime.now().astimezone().isoformat()),
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "ArticleDatabase":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
