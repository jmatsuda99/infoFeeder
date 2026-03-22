
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd
from article_utils import article_key

DB_PATH="data/alerts.db"

def get_conn():
    Path("data").mkdir(exist_ok=True)
    conn=sqlite3.connect(DB_PATH)
    conn.row_factory=sqlite3.Row
    return conn

def init_db():
    conn=get_conn()
    cur=conn.cursor()

    cur.execute("""CREATE TABLE IF NOT EXISTS feeds(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        url TEXT UNIQUE,
        base_url TEXT,
        source_type TEXT DEFAULT 'rss',
        category TEXT,
        is_active INTEGER DEFAULT 1,
        last_success_at TEXT,
        last_error_at TEXT,
        last_error_message TEXT,
        created_at TEXT,
        updated_at TEXT
    )""")

    feed_columns = {row["name"] for row in cur.execute("PRAGMA table_info(feeds)")}
    if "base_url" not in feed_columns:
        cur.execute("ALTER TABLE feeds ADD COLUMN base_url TEXT")
    if "source_type" not in feed_columns:
        cur.execute("ALTER TABLE feeds ADD COLUMN source_type TEXT DEFAULT 'rss'")
    if "last_success_at" not in feed_columns:
        cur.execute("ALTER TABLE feeds ADD COLUMN last_success_at TEXT")
    if "last_error_at" not in feed_columns:
        cur.execute("ALTER TABLE feeds ADD COLUMN last_error_at TEXT")
    if "last_error_message" not in feed_columns:
        cur.execute("ALTER TABLE feeds ADD COLUMN last_error_message TEXT")
    cur.execute("UPDATE feeds SET base_url=COALESCE(base_url, url) WHERE base_url IS NULL OR base_url = ''")
    cur.execute("UPDATE feeds SET source_type='rss' WHERE source_type IS NULL OR source_type = ''")

    cur.execute("""CREATE TABLE IF NOT EXISTS items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        feed_id INTEGER,
        title TEXT,
        link TEXT UNIQUE,
        article_key TEXT,
        published TEXT,
        summary TEXT,
        is_read INTEGER DEFAULT 0,
        fetched_at TEXT
    )""")

    item_columns = {row["name"] for row in cur.execute("PRAGMA table_info(items)")}
    if "article_key" not in item_columns:
        cur.execute("ALTER TABLE items ADD COLUMN article_key TEXT")
    if "is_read" not in item_columns:
        cur.execute("ALTER TABLE items ADD COLUMN is_read INTEGER DEFAULT 0")

    rows_to_backfill = cur.execute("""
        SELECT id, title, link
        FROM items
        WHERE article_key IS NULL OR article_key = ''
    """).fetchall()
    for row in rows_to_backfill:
        cur.execute(
            "UPDATE items SET article_key=? WHERE id=?",
            (article_key(row["title"], row["link"]), row["id"])
        )

    conn.commit()
    conn.close()

def add_feed(name,url,category="", source_type="rss", base_url=None):
    now=datetime.now().isoformat(timespec="seconds")
    conn=get_conn()
    cur=conn.cursor()

    try:
        cur.execute("""
        INSERT INTO feeds(name,url,base_url,source_type,category,is_active,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?)
        """,(name,url,base_url or url,source_type,category,1,now,now))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def list_feeds():
    conn=get_conn()
    cur=conn.cursor()
    cur.execute("""
        SELECT
            f.*,
            COUNT(i.id) AS item_count,
            MAX(i.fetched_at) AS last_fetched_at
        FROM feeds f
        LEFT JOIN items i ON i.feed_id = f.id
        GROUP BY f.id
        ORDER BY f.id DESC
    """)
    rows=cur.fetchall()
    conn.close()
    return rows

def update_feed_status(feed_id,is_active):
    conn=get_conn()
    cur=conn.cursor()
    cur.execute(
        "UPDATE feeds SET is_active=? WHERE id=?",
        (1 if is_active else 0,feed_id)
    )
    conn.commit()
    conn.close()

def delete_feed(feed_id):
    conn=get_conn()
    cur=conn.cursor()
    cur.execute("DELETE FROM feeds WHERE id=?", (feed_id,))
    conn.commit()
    conn.close()


def list_articles(keyword=""):
    conn = get_conn()

    query = """
    SELECT
        MAX(i.id) as id,
        MAX(i.published) as published,
        MAX(COALESCE(f.category, '')) as category,
        MAX(COALESCE(f.name, '')) as source_name,
        MAX(COALESCE(i.article_key, '')) as article_key,
        MAX(COALESCE(i.is_read, 0)) as is_read,
        i.link as link,
        MAX(i.title) as title,
        MAX(COALESCE(i.summary, '')) as summary
    FROM items i
    JOIN feeds f ON i.feed_id = f.id
    WHERE 1=1
    """

    params = []

    if keyword:
        query += " AND (i.title LIKE ? OR i.summary LIKE ?)"
        like = f"%{keyword}%"
        params.extend([like, like])

    query += """
    GROUP BY i.link
    ORDER BY MAX(COALESCE(i.published, '')) DESC, MAX(i.id) DESC
    """

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def update_article_read_status(article_key_value, is_read):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE items SET is_read=? WHERE article_key=?",
        (1 if is_read else 0, article_key_value)
    )
    conn.commit()
    conn.close()


def update_articles_read_status(article_keys, is_read):
    keys = [key for key in article_keys if key]
    if not keys:
        return

    conn = get_conn()
    cur = conn.cursor()
    placeholders = ",".join(["?"] * len(keys))
    cur.execute(
        f"UPDATE items SET is_read=? WHERE article_key IN ({placeholders})",
        [1 if is_read else 0, *keys]
    )
    conn.commit()
    conn.close()
