import sqlite3
from datetime import datetime
import feedparser

DB_PATH = "data/alerts.db"

def fetch_active_feeds():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("SELECT id, name, url FROM feeds WHERE is_active = 1")
    feeds = cur.fetchall()

    inserted = 0
    for feed_id, name, url in feeds:
        parsed = feedparser.parse(url)
        for entry in parsed.entries:
            cur.execute("""
                INSERT OR IGNORE INTO items
                (feed_id, title, link, published, summary, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                feed_id,
                entry.get("title", ""),
                entry.get("link", ""),
                entry.get("published", ""),
                entry.get("summary", ""),
                datetime.now().isoformat(timespec="seconds"),
            ))
            inserted += cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0

    conn.commit()
    conn.close()
    return inserted
