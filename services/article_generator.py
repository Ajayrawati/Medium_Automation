"""Grounded Gemini article generation from the approved evidence set."""

from __future__ import annotations

from datetime import date
import os

from models.topic import Evidence, GeneratedArticle, Topic


class GenerationError(RuntimeError):
    pass


def _evidence_prompt(evidence: list[Evidence]) -> str:
    entries = []
    for index, item in enumerate(evidence, start=1):
        entries.append(
            f"[{index}] {item.title}\nPublisher: {item.publisher}\nURL: {item.article_url}\n"
            f"Verified excerpt: {item.excerpt}"
        )
    return "\n\n".join(entries)


def generate_article(topic: Topic, evidence: list[Evidence], settings: dict, generated_for: date) -> GeneratedArticle:
    """Call Gemini only after topic confidence and evidence checks are complete."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise GenerationError("GEMINI_API_KEY is not configured")
    if not evidence:
        raise GenerationError("No verified evidence is available")

    from google import genai
    from google.genai import types

    min_words = int(settings.get("min_words", 500))
    max_words = int(settings.get("max_words", 800))
    prompt = f"""Write a factual news article about: {topic.title}

Confidence: {topic.confidence}/100. Use only the evidence below. Do not invent facts,
quotes, dates, numbers, images, or code. Attribute claims with bracket citations such as [1]. If sources
disagree or evidence is incomplete, say so. Return Medium-style Markdown: a level-one headline, a one-line italic
subtitle, a "## Key takeaways" section with three bullet points, and clear "##" sections. Produce a {min_words}-{max_words}
word article. Do not add a source list, an image, or a code block; the application adds verified assets separately.

EVIDENCE
{_evidence_prompt(evidence)}"""
    model = settings.get("model", "gemini-3.5-flash-lite")
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction="You are a careful journalist. Ground every claim in supplied evidence.",
            max_output_tokens=max_words * 2,
        ),
    )
    text = (response.text or "").strip()
    if not text:
        raise GenerationError("The generation model returned no text")
    headline, _, body = text.partition("\n")
    return GeneratedArticle(
        topic_key=topic.key,
        title=headline.lstrip("# ").strip() or topic.title,
        body=body.strip() or text,
        confidence=topic.confidence,
        generated_for=generated_for,
        sources=evidence,
        generator=model,
        cover_image=settings.get("cover_image_url") or None,
    )
