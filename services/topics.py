"""Deterministic topic clustering, confidence scoring, and voting."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import re
from typing import Iterable

from models.article import Article
from models.topic import Topic

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "in", "into",
    "is", "it", "its", "of", "on", "or", "that", "the", "this", "to", "was", "what", "when",
    "with", "will", "you", "your", "new", "news", "about", "after", "over", "than", "their",
}


def _tokens(article: Article) -> set[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{2,}", f"{article.title} {article.summary}".lower())
    return {word.strip(".-") for word in words if word.strip(".-") not in STOP_WORDS}


def _topic_label(articles: Iterable[Article]) -> tuple[str, str]:
    counts = Counter(token for article in articles for token in _tokens(article))
    terms = [term for term, _ in counts.most_common(3)] or ["general"]
    key = "-".join(terms[:3])
    return key, " ".join(term.capitalize() for term in terms[:3])


def cluster_topics(articles: list[Article]) -> list[Topic]:
    """Group related articles using title/summary token overlap."""
    clusters: list[list[Article]] = []
    cluster_tokens: list[set[str]] = []
    for article in articles:
        tokens = _tokens(article)
        if not tokens:
            continue
        best_index, best_similarity = None, 0.0
        for index, existing in enumerate(cluster_tokens):
            overlap = len(tokens & existing)
            similarity = overlap / max(1, min(len(tokens), len(existing)))
            if overlap >= 2 and similarity > best_similarity:
                best_index, best_similarity = index, similarity
        if best_index is None or best_similarity < 0.2:
            clusters.append([article])
            cluster_tokens.append(set(tokens))
        else:
            clusters[best_index].append(article)
            cluster_tokens[best_index].update(tokens)

    topics: list[Topic] = []
    for cluster in clusters:
        key, title = _topic_label(cluster)
        categories = Counter(article.category for article in cluster)
        topics.append(Topic(key=key, title=title, category=categories.most_common(1)[0][0], articles=cluster))
    return topics


def _recency_score(article: Article, now: datetime) -> float:
    if article.published_at is None:
        return 35.0
    published = article.published_at
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    hours = max(0.0, (now - published.astimezone(timezone.utc)).total_seconds() / 3600)
    return max(0.0, 100.0 * (1 - hours / 72))


def score_topics(topics: list[Topic], settings: dict, now: datetime | None = None) -> list[Topic]:
    """Assign transparent confidence and automatic vote values to candidates."""
    now = now or datetime.now(timezone.utc)
    category_weights = settings.get("category_weights", {})
    max_volume = max((len(topic.articles) for topic in topics), default=1)
    for topic in topics:
        source_quality = sum(float(article.metadata.get("source_reliability", 0.6)) * 100 for article in topic.articles)
        source_quality /= max(1, len(topic.articles))
        independent_sources = {article.metadata.get("publisher") or article.source for article in topic.articles}
        min_sources = max(1, int(settings.get("min_independent_sources", 2)))
        corroboration = min(100.0, len(independent_sources) / min_sources * 100)
        recency = sum(_recency_score(article, now) for article in topic.articles) / len(topic.articles)
        relevance = min(100.0, max(0.0, float(category_weights.get(topic.category, 1.0)) * 100))
        momentum = len(topic.articles) / max_volume * 100
        breakdown = {
            "source_quality": round(source_quality, 2),
            "corroboration": round(corroboration, 2),
            "recency": round(recency, 2),
            "relevance": round(relevance, 2),
            "momentum": round(momentum, 2),
        }
        weights = settings.get("confidence_weights", {})
        confidence = sum(breakdown[key] * float(weights.get(key, 0)) for key in breakdown)
        topic.score_breakdown = breakdown
        topic.confidence = round(confidence, 2)
        topic.automatic_vote = round(topic.confidence + min(10.0, len(independent_sources) * 2), 2)
    return topics


def apply_manual_votes(topics: list[Topic], votes: dict[str, float]) -> list[Topic]:
    for topic in topics:
        topic.manual_vote = float(votes.get(topic.key, votes.get(topic.title.lower(), 0)))
    return topics


def select_topic(topics: list[Topic], minimum_confidence: float, minimum_sources: int) -> Topic | None:
    eligible = [
        topic for topic in topics
        if topic.confidence >= minimum_confidence
        and len({article.metadata.get("publisher") or article.source for article in topic.articles}) >= minimum_sources
    ]
    return max(eligible, key=lambda item: (item.final_vote, item.confidence), default=None)
