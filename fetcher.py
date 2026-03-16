
import sqlite3
from datetime import datetime
from urllib.parse import urlparse, urlunparse, parse_qs, unquote
import feedparser

DB_PATH="data/alerts.db"

def normalize_url(url):
    try:
        parsed=urlparse(url)

        if "google." in parsed.netloc:
            qs=parse_qs(parsed.query)

            for key in ["url","q"]:
                if key in qs and qs[key]:
                    real=unquote(qs[key][0])
                    real_parsed=urlparse(real)
                    return urlunparse(real_parsed._replace(fragment=""))

        return urlunparse(parsed._replace(fragment=""))

    except Exception:
        return url

def fetch_active_feeds():

    conn=sqlite3.connect(DB_PATH)
    cur=conn.cursor()

    cur.execute("SELECT id,url FROM feeds WHERE is_active=1")
    feeds=cur.fetchall()

    inserted=0
    feed_entries=0

    for feed_id,url in feeds:

        parsed=feedparser.parse(url)
        entries=parsed.entries

        feed_entries+=len(entries)

        for e in entries:

            link=normalize_url(e.get("link",""))

            cur.execute("""
            INSERT OR IGNORE INTO items
            (feed_id,title,link,published,summary,fetched_at)
            VALUES(?,?,?,?,?,?)
            """,(
                feed_id,
                e.get("title",""),
                link,
                e.get("published",""),
                e.get("summary",""),
                datetime.now().isoformat(timespec="seconds")
            ))

            if cur.rowcount>0:
                inserted+=1

    conn.commit()
    conn.close()

    existing=max(feed_entries-inserted,0)

    return {
        "feeds":len(feeds),
        "feed_entries":feed_entries,
        "inserted":inserted,
        "existing":existing
    }
