import sqlite3
from datetime import datetime
from urllib.parse import urlparse, urlunparse
import feedparser

DB_PATH = "data/alerts.db"

def normalize_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        clean = parsed._replace(query="", fragment="")
        return urlunparse(clean)
    except Exception:
        return url

def fetch_active_feeds():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT id, name, url FROM feeds WHERE is_active = 1")
    feeds = cur.fetchall()

    inserted = 0
    for feed_id, name, url in feeds:
        parsed = feedparser.parse(url)
        for entry in parsed.entries:
            link = normalize_url(entry.get("link", ""))
            cur.execute("""
                INSERT OR IGNORE INTO items
                (feed_id, title, link, published, summary, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                feed_id,
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
