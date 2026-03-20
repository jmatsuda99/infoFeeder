
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

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
        category TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT,
        updated_at TEXT
    )""")

    cur.execute("""CREATE TABLE IF NOT EXISTS items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        feed_id INTEGER,
        title TEXT,
        link TEXT UNIQUE,
        published TEXT,
        summary TEXT,
        fetched_at TEXT
    )""")

    conn.commit()
    conn.close()

def add_feed(name,url,category=""):
    now=datetime.now().isoformat(timespec="seconds")
    conn=get_conn()
    cur=conn.cursor()

    try:
        cur.execute("""
        INSERT INTO feeds(name,url,category,is_active,created_at,updated_at)
        VALUES(?,?,?,?,?,?)
        """,(name,url,category,1,now,now))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def list_feeds():
    conn=get_conn()
    cur=conn.cursor()
    cur.execute("SELECT * FROM feeds ORDER BY id DESC")
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
