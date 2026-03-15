
import sqlite3
from datetime import datetime
from urllib.parse import urlparse,urlunparse
import feedparser
DB_PATH="data/alerts.db"
def normalize_url(url):
    try:
        p=urlparse(url)
        return urlunparse(p._replace(query="",fragment=""))
    except:
        return url
def fetch_active_feeds():
    conn=sqlite3.connect(DB_PATH);cur=conn.cursor()
    cur.execute("SELECT id,name,url FROM feeds WHERE is_active=1")
    feeds=cur.fetchall()
    inserted=0
    for feed_id,name,url in feeds:
        parsed=feedparser.parse(url)
        for e in parsed.entries:
            link=normalize_url(e.get("link",""))
            cur.execute("""INSERT OR IGNORE INTO items
            (feed_id,title,link,published,summary,fetched_at)
            VALUES(?,?,?,?,?,?)""",(
            feed_id,e.get("title",""),link,e.get("published",""),
            e.get("summary",""),datetime.now().isoformat(timespec="seconds")))
            if cur.rowcount>0: inserted+=1
    conn.commit();conn.close();return inserted
