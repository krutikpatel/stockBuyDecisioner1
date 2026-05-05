from __future__ import annotations

import json
import logging
from typing import Optional

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore

from app.config import settings
from app.models.news import NewsItem, NewsSummary

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword-based fallback classifier
# ---------------------------------------------------------------------------

_POSITIVE_KEYWORDS = [
    "beat", "beats", "raised guidance", "upgrade", "upgraded", "price target raised",
    "strong earnings", "record revenue", "customer win", "partnership", "fda approval",
    "regulatory approval", "buyback", "dividend increase", "expansion", "growth",
    "profit", "outperform", "buy rating", "insider buying", "acquisition approved",
]

_NEGATIVE_KEYWORDS = [
    "miss", "missed", "guidance cut", "downgrade", "downgraded", "price target cut",
    "earnings miss", "revenue miss", "layoffs", "lawsuit", "investigation", "recall",
    "margin pressure", "slower growth", "loss", "bankruptcy", "debt", "dilution",
    "regulatory probe", "class action", "insider selling", "product recall",
]

_IMPORTANCE_HIGH = ["earnings", "guidance", "fda", "acquisition", "merger", "sec", "investigation", "bankruptcy"]
_IMPORTANCE_MEDIUM = ["upgrade", "downgrade", "analyst", "partnership", "buyback", "dividend"]

_CATEGORY_MAP = {
    "legal": ["lawsuit", "investigation", "sec", "class action", "probe", "regulatory"],
    "earnings": ["earnings", "eps", "revenue", "quarterly results"],
    "analyst": ["upgrade", "downgrade", "price target", "analyst"],
    "management": ["ceo", "cfo", "executive", "resign", "appoint", "hire"],
    "macro": ["federal reserve", "inflation", "interest rate", "economy", "gdp"],
    "sector": ["industry", "sector", "competitor", "market share"],
    "product": ["launch", "product", "fda", "approval", "recall"],
}


def _keyword_classify(title: str) -> tuple[str, str, str]:
    text = title.lower()
    sentiment = "neutral"
    pos_hits = sum(1 for kw in _POSITIVE_KEYWORDS if kw in text)
    neg_hits = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in text)
    if pos_hits > neg_hits:
        sentiment = "positive"
    elif neg_hits > pos_hits:
        sentiment = "negative"

    importance = "low"
    if any(kw in text for kw in _IMPORTANCE_HIGH):
        importance = "high"
    elif any(kw in text for kw in _IMPORTANCE_MEDIUM):
        importance = "medium"

    category = "other"
    for cat, keywords in _CATEGORY_MAP.items():
        if any(kw in text for kw in keywords):
            category = cat
            break

    return sentiment, importance, category


# ---------------------------------------------------------------------------
# OpenAI-based classifier
# ---------------------------------------------------------------------------

def _openai_classify_batch(items: list[NewsItem]) -> list[NewsItem]:
    if OpenAI is None:
        logger.warning("openai package not installed; using keyword fallback")
        return _keyword_classify_batch(items)

    client = OpenAI(api_key=settings.openai_api_key)

    titles = [f'{i + 1}. {item.title}' for i, item in enumerate(items)]
    prompt = (
        "You are a financial news sentiment classifier.\n"
        "For each numbered news headline below, return a JSON array where each element has:\n"
        '  "sentiment": "positive" | "neutral" | "negative"\n'
        '  "importance": "low" | "medium" | "high"\n'
        '  "category": "earnings" | "analyst" | "product" | "legal" | "macro" | "sector" | "management" | "other"\n\n'
        "Headlines:\n" + "\n".join(titles) + "\n\n"
        "Return ONLY a valid JSON array, no explanation."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=1024,
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        classifications = json.loads(raw)
        for i, cls in enumerate(classifications):
            if i >= len(items):
                break
            items[i].sentiment = cls.get("sentiment", "neutral")
            items[i].importance = cls.get("importance", "low")
            items[i].category = cls.get("category", "other")
    except Exception as e:
        logger.warning("OpenAI classification failed: %s — falling back to keywords", e)
        return _keyword_classify_batch(items)

    return items


def _keyword_classify_batch(items: list[NewsItem]) -> list[NewsItem]:
    for item in items:
        s, imp, cat = _keyword_classify(item.title)
        item.sentiment = s
        item.importance = imp
        item.category = cat
    return items


# ---------------------------------------------------------------------------
# News score (§11.3)
# ---------------------------------------------------------------------------

def _compute_news_score(items: list[NewsItem]) -> float:
    if not items:
        return 50.0

    weighted_score = 0.0
    total_weight = 0.0
    importance_weights = {"high": 3.0, "medium": 2.0, "low": 1.0}
    sentiment_values = {"positive": 1.0, "neutral": 0.0, "negative": -1.0}

    for item in items:
        w = importance_weights.get(item.importance, 1.0)
        v = sentiment_values.get(item.sentiment, 0.0)
        weighted_score += w * v
        total_weight += w

    if total_weight == 0:
        return 50.0

    ratio = weighted_score / total_weight  # in [-1, 1]
    # Map to [0, 100]: 0 → 0, 1 → 100, -1 → 0 with center at 50
    score = 50.0 + ratio * 40.0
    return round(max(0.0, min(100.0, score)), 2)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def classify_news(items: list[NewsItem]) -> NewsSummary:
    if not items:
        return NewsSummary(news_score=50.0, coverage_limited=True)

    if settings.openai_api_key:
        classified = _openai_classify_batch(list(items))
    else:
        logger.info("OPENAI_API_KEY not set — using keyword classifier")
        classified = _keyword_classify_batch(list(items))

    pos = sum(1 for i in classified if i.sentiment == "positive")
    neg = sum(1 for i in classified if i.sentiment == "negative")
    neu = sum(1 for i in classified if i.sentiment == "neutral")
    news_score = _compute_news_score(classified)

    return NewsSummary(
        items=classified,
        positive_count=pos,
        negative_count=neg,
        neutral_count=neu,
        news_score=news_score,
        coverage_limited=True,
    )
