
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = "data/alerts.db"

def get_conn():
    Path("data").mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS feeds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        url TEXT UNIQUE,
        category TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        feed_id INTEGER,
        title TEXT,
        link TEXT UNIQUE,
        published TEXT,
        summary TEXT,
        fetched_at TEXT,
        FOREIGN KEY(feed_id) REFERENCES feeds(id)
    )
    """)

    conn.commit()

    _migrate_feeds_table(conn)
    conn.close()

def _get_columns(conn, table_name):
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table_name})")
    return [row["name"] for row in cur.fetchall()]

def _migrate_feeds_table(conn):
    cols = _get_columns(conn, "feeds")
    required = ["id", "name", "url", "category", "is_active", "created_at", "updated_at"]
    if cols == required:
        return

    cur = conn.cursor()
    cur.execute("ALTER TABLE feeds RENAME TO feeds_old")
    cur.execute("""
    CREATE TABLE feeds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        url TEXT UNIQUE,
        category TEXT,
        is_active INTEGER DEFAULT 1,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    old_cols = _get_columns(conn, "feeds_old")
    select_parts = []
    for col in ["id", "name", "url", "category", "is_active", "created_at", "updated_at"]:
        if col in old_cols:
            select_parts.append(col)
        elif col == "category":
            select_parts.append("'' AS category")
        elif col == "is_active":
            select_parts.append("1 AS is_active")
        elif col in ("created_at", "updated_at"):
            select_parts.append("'' AS " + col)
        else:
            select_parts.append("NULL AS " + col)

    cur.execute(f"""
    INSERT INTO feeds (id, name, url, category, is_active, created_at, updated_at)
    SELECT {", ".join(select_parts)}
    FROM feeds_old
    """)
    cur.execute("DROP TABLE feeds_old")
    conn.commit()

def add_feed(name, url, category=""):
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO feeds (name, url, category, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, url, category, 1, now, now))
    conn.commit()
    conn.close()

def list_feeds():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, url, category, is_active, created_at, updated_at
        FROM feeds
        ORDER BY id DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

def update_feed_status(feed_id, is_active):
    now = datetime.now().isoformat(timespec="seconds")
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        UPDATE feeds
        SET is_active = ?, updated_at = ?
        WHERE id = ?
    """, (1 if is_active else 0, now, feed_id))
    conn.commit()
    conn.close()

def delete_feed(feed_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
    conn.commit()
    conn.close()
