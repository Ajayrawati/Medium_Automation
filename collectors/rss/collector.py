"""RSS collector."""

from __future__ import annotations

from urllib.parse import urlsplit

from collectors.rss.parser import parse_feed
from models.article import Article


class RSSCollector:
    def collect(self, source: dict, limit: int) -> list[Article]:
        articles = parse_feed(source["url"], source["name"], source.get("category", "general"))
        for article in articles:
            article.metadata.update({
                "source_reliability": float(source.get("reliability", 0.65)),
                "publisher": source.get("publisher") or urlsplit(article.url).netloc or source["name"],
            })
        return articles[:limit]
