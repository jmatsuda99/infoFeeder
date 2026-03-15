import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd

DB_PATH = Path("data/alerts.db")


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def init_db() -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            category TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            last_checked_at TEXT,
            last_error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feed_id INTEGER NOT NULL,
            title TEXT,
            link TEXT NOT NULL UNIQUE,
            domain TEXT,
            published TEXT,
            summary TEXT,
            fetched_at TEXT NOT NULL,
            FOREIGN KEY(feed_id) REFERENCES feeds(id)
        )
        """
    )
    conn.commit()
    conn.close()


def add_feed(name: str, url: str, category: str = "") -> None:
    ts = now_iso()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO feeds (name, url, category, is_active, last_checked_at, last_error, created_at, updated_at)
        VALUES (?, ?, ?, 1, NULL, NULL, ?, ?)
        """,
        (name, url, category, ts, ts),
    )
    conn.commit()
    conn.close()


def list_feeds():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, name, url, category, is_active, last_checked_at, last_error, created_at, updated_at
        FROM feeds
        ORDER BY id DESC
        """
    )
    rows = [tuple(row) for row in cur.fetchall()]
    conn.close()
    return rows


def get_feed_by_id(feed_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM feeds WHERE id = ?", (feed_id,))
    row = cur.fetchone()
    conn.close()
    return tuple(row) if row else None


def update_feed(feed_id: int, name: str, url: str, category: str = "") -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE feeds
        SET name = ?, url = ?, category = ?, updated_at = ?, last_error = NULL
        WHERE id = ?
        """,
        (name, url, category, now_iso(), feed_id),
    )
    conn.commit()
    conn.close()


def update_feed_status(feed_id: int, is_active: bool) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE feeds SET is_active = ?, updated_at = ? WHERE id = ?",
        (1 if is_active else 0, now_iso(), feed_id),
    )
    conn.commit()
    conn.close()


def delete_feed(feed_id: int) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM items WHERE feed_id = ?", (feed_id,))
    cur.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
    conn.commit()
    conn.close()


def set_feed_check_result(feed_id: int, error: str | None = None) -> None:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE feeds SET last_checked_at = ?, last_error = ?, updated_at = ? WHERE id = ?",
        (now_iso(), error, now_iso(), feed_id),
    )
    conn.commit()
    conn.close()


def insert_item(feed_id: int, title: str, link: str, published: str, summary: str) -> bool:
    domain = urlparse(link).netloc if link else ""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT OR IGNORE INTO items (feed_id, title, link, domain, published, summary, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (feed_id, title, link, domain, published, summary, now_iso()),
    )
    inserted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return inserted


def list_categories() -> list[str]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT category FROM feeds WHERE category IS NOT NULL AND category <> '' ORDER BY category")
    rows = [row[0] for row in cur.fetchall()]
    conn.close()
    return rows


def search_items(
    keyword: str = "",
    category: str | None = None,
    feed_name: str | None = None,
    only_active: bool = True,
    limit: int = 100,
) -> pd.DataFrame:
    conn = get_conn()
    query = """
        SELECT
            i.id,
            i.published,
            i.title,
            i.link,
            i.domain,
            i.summary,
            f.name AS feed_name,
            f.category,
            f.is_active
        FROM items i
        JOIN feeds f ON i.feed_id = f.id
        WHERE 1 = 1
    """
    params: list[object] = []
    if keyword:
        query += " AND (i.title LIKE ? OR i.summary LIKE ? OR i.link LIKE ?)"
        like = f"%{keyword}%"
        params.extend([like, like, like])
    if category:
        query += " AND f.category = ?"
        params.append(category)
    if feed_name:
        query += " AND f.name = ?"
        params.append(feed_name)
    if only_active:
        query += " AND f.is_active = 1"
    query += " ORDER BY COALESCE(i.published, i.fetched_at) DESC, i.id DESC LIMIT ?"
    params.append(limit)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df
