"""Base interface for HTML collectors."""

from __future__ import annotations

from typing import Protocol

from models.article import Article


class ScraperCollector(Protocol):
    def collect(self, source: dict, limit: int) -> list[Article]: ...
