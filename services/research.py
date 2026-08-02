"""Evidence re-checking for the chosen topic."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

from models.article import Article
from models.topic import Evidence, Topic
from services.cleaner import clean_text


def _publisher(article: Article) -> str:
    return str(article.metadata.get("publisher") or urlsplit(article.url).netloc.lower() or article.source)


def _fetch_material(url: str) -> tuple[str, str]:
    response = requests.get(url, timeout=15, headers={"User-Agent": "TopicResearchBot/1.0 (+https://github.com)"})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    description = soup.select_one('meta[name="description"], meta[property="og:description"]')
    if description and description.get("content"):
        excerpt = clean_text(description["content"])[:1_200]
    else:
        paragraphs = [clean_text(node.get_text(" ", strip=True)) for node in soup.select("article p, main p, p")]
        excerpt = clean_text(" ".join(part for part in paragraphs if part))[:1_200]
    code_node = soup.select_one("pre code")
    code = code_node.get_text("\n", strip=True)[:1_500] if code_node else ""
    return excerpt, code


def collect_evidence(topic: Topic, passes: int, max_items: int) -> list[Evidence]:
    """Re-fetch selected links; retain source summaries if direct retrieval fails."""
    evidence: list[Evidence] = []
    seen_publishers: set[str] = set()
    candidates = sorted(topic.articles, key=lambda article: article.score or 0, reverse=True)
    for _ in range(max(1, passes)):
        for article in candidates:
            if len(evidence) >= max_items:
                break
            publisher = _publisher(article)
            if publisher in seen_publishers:
                continue
            excerpt = article.summary
            code_snippet = ""
            status = "source-summary"
            try:
                fetched, code_snippet = _fetch_material(article.url)
                if fetched:
                    excerpt, status = fetched, "rechecked"
            except requests.RequestException:
                pass
            if not excerpt:
                continue
            seen_publishers.add(publisher)
            evidence.append(Evidence(
                article_url=article.url,
                source=article.source,
                publisher=publisher,
                title=article.title,
                excerpt=excerpt,
                reliability=float(article.metadata.get("source_reliability", 0.6)),
                collected_at=datetime.now(timezone.utc),
                retrieval_status=status,
                code_snippet=code_snippet,
            ))
        if len(evidence) >= max_items:
            break
    corroborated = len(evidence) > 1
    for item in evidence:
        item.corroborated = corroborated
    return evidence
