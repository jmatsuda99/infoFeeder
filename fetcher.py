import json
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import feedparser

DB_PATH = "data/alerts.db"
FEEDS_PATH = "feeds.json"


def load_feeds():
    path = Path(FEEDS_PATH)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def normalize_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        clean = parsed._replace(query="", fragment="")
        return urlunparse(clean)
    except Exception:
        return url


def fetch_active_feeds():
    feeds = [f for f in load_feeds() if f.get("is_active", True)]
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    inserted = 0
    for feed in feeds:
        feed_name = feed.get("name", "")
        category = feed.get("category", "")
        url = feed.get("url", "")
        parsed = feedparser.parse(url)

        for entry in parsed.entries:
            link = normalize_url(entry.get("link", ""))

            cur.execute("""
                INSERT OR IGNORE INTO items
                (feed_name, category, title, link, published, summary, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                feed_name,
                category,
                entry.get("title", ""),
                link,
                entry.get("published", ""),
                entry.get("summary", ""),
                datetime.now().isoformat(timespec="seconds"),
            ))

            inserted += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0

    conn.commit()
    conn.close()
    return inserted
