from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import yfinance as yf

from app.models.news import NewsItem

logger = logging.getLogger(__name__)


def get_news_items(ticker: str, limit: int = 20) -> list[NewsItem]:
    items: list[NewsItem] = []
    try:
        t = yf.Ticker(ticker)
        raw_news = t.news
        if not raw_news:
            return items
        for article in raw_news[:limit]:
            title = article.get("title") or article.get("headline", "")
            if not title:
                continue
            pub_ts = article.get("providerPublishTime") or article.get("publishedAt")
            pub_str: Optional[str] = None
            if pub_ts:
                try:
                    pub_str = datetime.fromtimestamp(int(pub_ts), tz=timezone.utc).isoformat()
                except Exception:
                    pub_str = str(pub_ts)

            url = article.get("link") or article.get("url")
            source = (article.get("publisher") or article.get("source") or {})
            if isinstance(source, dict):
                source = source.get("name", "")

            items.append(
                NewsItem(
                    title=title,
                    source=source or None,
                    published_at=pub_str,
                    url=url,
                )
            )
    except Exception as e:
        logger.warning("Failed to fetch news for %s: %s", ticker, e)

    return items
