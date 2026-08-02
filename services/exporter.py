"""Human-readable exports for selected and generated topics."""

from __future__ import annotations

import json
from pathlib import Path

from models.topic import Evidence, GeneratedArticle, Topic


def export_topic_report(topic: Topic, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {topic.title}",
        "",
        f"Confidence: {topic.confidence:.2f}/100",
        f"Automatic vote: {topic.automatic_vote:.2f}",
        f"Manual vote: {topic.manual_vote:.2f}",
        f"Final vote: {topic.final_vote:.2f}",
        "",
        "## Score breakdown",
        "",
    ]
    lines.extend(f"- {label.replace('_', ' ').title()}: {value:.2f}" for label, value in topic.score_breakdown.items())
    lines.extend(("", "## Candidate articles", ""))
    lines.extend(f"- [{article.title}]({article.url}) — {article.source}" for article in topic.articles)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_generated_article(article: GeneratedArticle, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {article.title}",
        "",
        f"**Topic confidence:** {article.confidence:.2f}/100",
        f"**Generated:** {article.generated_for.isoformat()}",
        "",
    ]
    if article.cover_image:
        lines.extend((f"![Cover image]({article.cover_image})", "*Cover image — use only licensed or original artwork.*", ""))
    else:
        lines.extend(("> **Cover visual:** Add a licensed or original wide image that represents this topic.", ""))
    lines.extend((article.body, ""))
    code_evidence = next((item for item in article.sources if item.code_snippet), None)
    if code_evidence:
        lines.extend((
            "## Verified code example",
            "",
            f"From [{code_evidence.title}]({code_evidence.article_url}).",
            "",
            "```text",
            code_evidence.code_snippet,
            "```",
            "",
        ))
    lines.extend(("## Sources", ""))
    lines.extend(f"{index}. [{source.title}]({source.article_url}) — {source.publisher}" for index, source in enumerate(article.sources, start=1))
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_evidence_audit(topic: Topic, evidence: list[Evidence], path: str | Path) -> None:
    """Create a machine-readable, version-control-friendly research audit."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "topic": topic.title,
        "topic_key": topic.key,
        "confidence": topic.confidence,
        "score_breakdown": topic.score_breakdown,
        "final_vote": topic.final_vote,
        "evidence": [
            {
                "title": item.title,
                "url": item.article_url,
                "publisher": item.publisher,
                "source": item.source,
                "reliability": item.reliability,
                "corroborated": item.corroborated,
                "retrieval_status": item.retrieval_status,
                "has_code_snippet": bool(item.code_snippet),
                "collected_at": item.collected_at.isoformat(),
            }
            for item in evidence
        ],
    }
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
