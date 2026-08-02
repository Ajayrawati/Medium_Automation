"""GitHub Trending page collector."""

from __future__ import annotations

from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from models.article import Article


class GitHubTrendingCollector:
    URL = "https://github.com/trending"

    def collect(self, source: dict, limit: int) -> list[Article]:
        response = requests.get(self.URL, timeout=15, headers={"User-Agent": "AutomationCollector/1.0"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        articles: list[Article] = []
        for repository in soup.select("article.Box-row")[:limit]:
            link = repository.select_one("h2 a")
            if not link or not link.get("href"):
                continue
            name = " ".join(link.get_text(" ", strip=True).split())
            description = repository.select_one("p")
            articles.append(Article(
                title=name,
                url=urljoin("https://github.com", link["href"]),
                source=source.get("name", "GitHub Trending"),
                category=source.get("category", "technology"),
                summary=description.get_text(" ", strip=True) if description else "",
                metadata={
                    "source_reliability": float(source.get("reliability", 0.7)),
                    "publisher": source.get("publisher", "GitHub"),
                },
            ))
        return articles
