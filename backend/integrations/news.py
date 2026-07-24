"""News integration using RSS feeds — no API key required.

Reads news headlines from public RSS feeds. Supports multiple sources
with category filtering (tech, general, business, science).

Usage:
    news = NewsClient()
    headlines = await news.get_headlines(category="technology", max_items=5)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger("may.integrations.news")

# Free RSS feeds organized by category — no API keys needed
RSS_FEEDS = {
    "technology": [
        ("Hacker News (best)", "https://hnrss.org/best?count=10"),
        ("TechCrunch", "https://techcrunch.com/feed/"),
        ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
        ("The Verge", "https://www.theverge.com/rss/index.xml"),
    ],
    "general": [
        ("Reuters", "https://www.reutersagency.com/feed/?best-topics=tech&post_type=best"),
        ("BBC News", "https://feeds.bbci.co.uk/news/rss.xml"),
        ("AP News", "https://rsshub.app/apnews/topics/apf-topnews"),
    ],
    "science": [
        ("Science Daily", "https://www.sciencedaily.com/rss/all.xml"),
        ("Phys.org", "https://phys.org/rss-feed/"),
    ],
    "business": [
        ("CNBC", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147"),
        ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories"),
    ],
}


@dataclass
class NewsItem:
    """A single news headline."""
    title: str
    link: str
    source: str
    published: str = ""
    summary: str = ""
    category: str = "general"


@dataclass
class NewsDigest:
    """A collection of news headlines."""
    category: str
    items: list[NewsItem] = field(default_factory=list)
    fetched_at: float = 0

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "count": len(self.items),
            "fetched_at": self.fetched_at,
            "items": [
                {"title": i.title, "link": i.link, "source": i.source,
                 "summary": i.summary[:200] if i.summary else ""}
                for i in self.items
            ],
        }

    def to_briefing_text(self, max_items: int = 5) -> str:
        """Format as natural-language briefing text."""
        if not self.items:
            return "No headlines available right now."
        lines = [f"Top {self.category} headlines:"]
        for i, item in enumerate(self.items[:max_items]):
            lines.append(f"  {i+1}. {item.title} ({item.source})")
        return "\n".join(lines)


class NewsClient:
    """Fetches news from public RSS feeds (no API key needed)."""

    def __init__(self):
        self._cache: dict[str, tuple[float, NewsDigest]] = {}
        self._cache_ttl = 600  # 10 minutes

    async def get_headlines(self, category: str = "technology",
                            max_items: int = 5) -> NewsDigest:
        """Get top headlines for a category.

        Args:
            category: One of "technology", "general", "science", "business"
            max_items: Maximum headlines to return

        Returns:
            NewsDigest with parsed headlines
        """
        # Check cache
        cached = self._cache.get(category)
        if cached and (time.time() - cached[0]) < self._cache_ttl:
            return cached[1]

        try:
            import feedparser
        except ImportError:
            logger.error("feedparser not installed. Run: pip install feedparser")
            return NewsDigest(category=category, fetched_at=time.time())

        feeds = RSS_FEEDS.get(category, RSS_FEEDS["general"])
        items = []

        # Fetch all feeds for this category concurrently
        async def _fetch_one(name: str, url: str) -> list[NewsItem]:
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(url, headers={
                        "User-Agent": "MayAI/1.0 (RSS Reader)"
                    })
                    resp.raise_for_status()

                feed = feedparser.parse(resp.text)
                result = []
                for entry in feed.entries[:5]:
                    result.append(NewsItem(
                        title=entry.get("title", "").strip(),
                        link=entry.get("link", ""),
                        source=name,
                        published=entry.get("published", ""),
                        summary=entry.get("summary", "")[:300],
                        category=category,
                    ))
                return result
            except Exception as e:
                logger.debug("Failed to fetch RSS from %s: %s", name, e)
                return []

        tasks = [_fetch_one(name, url) for name, url in feeds]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                items.extend(result)

        # Deduplicate by title similarity
        seen_titles = set()
        unique_items = []
        for item in items:
            title_key = item.title.lower()[:50]
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                unique_items.append(item)

        digest = NewsDigest(
            category=category,
            items=unique_items[:max_items],
            fetched_at=time.time(),
        )

        # Cache the result
        self._cache[category] = (time.time(), digest)

        logger.info("News: fetched %d %s headlines", len(digest.items), category)
        return digest

    async def get_morning_news(self) -> dict[str, NewsDigest]:
        """Get headlines across multiple categories for the morning briefing."""
        categories = ["technology", "general"]
        results = {}
        for cat in categories:
            results[cat] = await self.get_headlines(cat, max_items=3)
        return results
