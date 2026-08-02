"""Domain models for topic selection, evidence, and generated articles."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from models.article import Article


@dataclass(slots=True)
class Topic:
    key: str
    title: str
    category: str
    articles: list[Article]
    confidence: float = 0.0
    score_breakdown: dict[str, float] = field(default_factory=dict)
    automatic_vote: float = 0.0
    manual_vote: float = 0.0

    @property
    def final_vote(self) -> float:
        return round(self.automatic_vote + self.manual_vote, 2)


@dataclass(slots=True)
class Evidence:
    article_url: str
    source: str
    publisher: str
    title: str
    excerpt: str
    reliability: float
    collected_at: datetime
    corroborated: bool = False
    retrieval_status: str = "source-summary"
    code_snippet: str = ""


@dataclass(slots=True)
class GeneratedArticle:
    topic_key: str
    title: str
    body: str
    confidence: float
    generated_for: date
    sources: list[Evidence]
    generator: str
    cover_image: str | None = None
