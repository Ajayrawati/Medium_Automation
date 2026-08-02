"""Hacker News API collector."""

from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import urlsplit

import requests

from models.article import Article

BASE_URL = "https://hacker-news.firebaseio.com/v0"


class HackerNewsCollector:
    def collect(self, source: dict, limit: int) -> list[Article]:
        response = requests.get(f"{BASE_URL}/topstories.json", timeout=15)
        response.raise_for_status()
        articles: list[Article] = []
        for item_id in response.json()[:limit * 3]:
            item_response = requests.get(f"{BASE_URL}/item/{item_id}.json", timeout=15)
            item_response.raise_for_status()
            item = item_response.json() or {}
            if item.get("type") != "story" or not item.get("title"):
                continue
            articles.append(Article(
                title=item["title"],
                url=item.get("url", f"https://news.ycombinator.com/item?id={item_id}"),
                source=source.get("name", "Hacker News"),
                category=source.get("category", "technology"),
                score=item.get("score"),
                published_at=datetime.fromtimestamp(item["time"], tz=timezone.utc) if item.get("time") else None,
                metadata={
                    "hackernews_id": item_id,
                    "comments": item.get("descendants", 0),
                    "source_reliability": float(source.get("reliability", 0.6)),
                    "publisher": source.get("publisher") or urlsplit(item.get("url", "")).netloc or "Hacker News",
                },
            ))
            if len(articles) >= limit:
                break
        return articles
