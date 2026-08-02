"""Small, dependency-free text normalization helpers."""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser

from models.article import Article


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def clean_text(value: str | None) -> str:
    """Strip HTML and collapse whitespace while keeping readable plain text."""
    if not value:
        return ""
    parser = _TextExtractor()
    parser.feed(unescape(value))
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def clean_article(article: Article) -> Article:
    """Normalize the fields used for display and matching."""
    article.title = clean_text(article.title)
    article.summary = clean_text(article.summary)
    article.url = article.url.strip()
    article.source = clean_text(article.source)
    article.category = clean_text(article.category).lower() or "general"
    return article
