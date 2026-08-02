"""Shared article model used by every collector."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Article:
    title: str
    url: str
    source: str
    category: str = "general"
    summary: str = ""
    published_at: datetime | None = None
    score: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        data = asdict(self)
        data["published_at"] = self.published_at.isoformat() if self.published_at else None
        return data
