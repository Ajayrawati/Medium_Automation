"""RSS/Atom feed parsing."""

from __future__ import annotations

from datetime import datetime
from email.utils import parsedate_to_datetime

import feedparser
import requests

from models.article import Article


def _published(entry: object) -> datetime | None:
    value = getattr(entry, "published", None) or getattr(entry, "updated", None)
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def parse_feed(url: str, source: str, category: str, timeout: int = 15) -> list[Article]:
    response = requests.get(url, timeout=timeout, headers={"User-Agent": "AutomationCollector/1.0"})
    response.raise_for_status()
    feed = feedparser.parse(response.content)
    if feed.bozo and not feed.entries:
        raise ValueError(f"Invalid feed from {url}")
    return [
        Article(
            title=entry.get("title", ""),
            url=entry.get("link", ""),
            source=source,
            category=category,
            summary=entry.get("summary", entry.get("description", "")),
            published_at=_published(entry),
        )
        for entry in feed.entries
        if entry.get("title") and entry.get("link")
    ]
