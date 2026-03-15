
import sqlite3
from datetime import datetime
import feedparser

DB_PATH="data/alerts.db"

def fetch_active_feeds():

    conn=sqlite3.connect(DB_PATH)
    cur=conn.cursor()

    cur.execute("SELECT id,url FROM feeds WHERE is_active=1")
    feeds=cur.fetchall()

    inserted=0

    for feed_id,url in feeds:

        parsed=feedparser.parse(url)

        for e in parsed.entries:

            cur.execute("""
            INSERT OR IGNORE INTO items
            (feed_id,title,link,published,summary,fetched_at)
            VALUES(?,?,?,?,?,?)
            """,(
                feed_id,
                e.get("title",""),
                e.get("link",""),
                e.get("published",""),
                e.get("summary",""),
                datetime.now().isoformat(timespec="seconds")
            ))

            if cur.rowcount>0:
                inserted+=1

    conn.commit()
    conn.close()

    return inserted
