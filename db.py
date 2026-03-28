
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from article_utils import article_key
from exclusion_rules import resolve_excluded_domain_keywords

DB_PATH="data/alerts.db"
DB_TIMEOUT_SECONDS = 30
DB_BUSY_TIMEOUT_MS = DB_TIMEOUT_SECONDS * 1000
DB_RETRY_ATTEMPTS = 5
DB_RETRY_DELAY_SECONDS = 0.4
EXCLUDED_DOMAIN_KEYWORDS = resolve_excluded_domain_keywords()


def configure_conn(conn):
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {DB_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def is_locked_error(error):
    return "database is locked" in str(error).lower()


def run_with_retry(action, *, retries=DB_RETRY_ATTEMPTS, delay=DB_RETRY_DELAY_SECONDS):
    last_error = None
    for attempt in range(retries):
        try:
            return action()
        except sqlite3.OperationalError as error:
            if not is_locked_error(error):
                raise
            last_error = error
            if attempt == retries - 1:
                raise
            time.sleep(delay * (attempt + 1))
    raise last_error


def get_conn():
    Path("data").mkdir(exist_ok=True)
    return run_with_retry(
        lambda: configure_conn(sqlite3.connect(DB_PATH, timeout=DB_TIMEOUT_SECONDS))
    )

def init_db():
    def _init():
        conn = get_conn()
        cur = conn.cursor()

        try:
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

            feed_needs_base_url = cur.execute(
                "SELECT 1 FROM feeds WHERE base_url IS NULL OR base_url = '' LIMIT 1"
            ).fetchone()
            if feed_needs_base_url:
                cur.execute("UPDATE feeds SET base_url=COALESCE(base_url, url) WHERE base_url IS NULL OR base_url = ''")

            feed_needs_source_type = cur.execute(
                "SELECT 1 FROM feeds WHERE source_type IS NULL OR source_type = '' LIMIT 1"
            ).fetchone()
            if feed_needs_source_type:
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
                is_saved INTEGER DEFAULT 0,
                saved_at TEXT,
                fetched_at TEXT
            )""")

            item_columns = {row["name"] for row in cur.execute("PRAGMA table_info(items)")}
            if "article_key" not in item_columns:
                cur.execute("ALTER TABLE items ADD COLUMN article_key TEXT")
            if "is_read" not in item_columns:
                cur.execute("ALTER TABLE items ADD COLUMN is_read INTEGER DEFAULT 0")
            if "is_saved" not in item_columns:
                cur.execute("ALTER TABLE items ADD COLUMN is_saved INTEGER DEFAULT 0")
            if "saved_at" not in item_columns:
                cur.execute("ALTER TABLE items ADD COLUMN saved_at TEXT")

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
        finally:
            conn.close()

    run_with_retry(_init)

def add_feed(name,url,category="", source_type="rss", base_url=None):
    now=datetime.now().isoformat(timespec="seconds")

    def _add_feed():
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

    return run_with_retry(_add_feed)

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
    def _update_feed_status():
        conn=get_conn()
        cur=conn.cursor()
        try:
            cur.execute(
                "UPDATE feeds SET is_active=? WHERE id=?",
                (1 if is_active else 0,feed_id)
            )
            conn.commit()
        finally:
            conn.close()

    run_with_retry(_update_feed_status)

def delete_feed(feed_id):
    def _delete_feed():
        conn=get_conn()
        cur=conn.cursor()
        try:
            cur.execute("DELETE FROM feeds WHERE id=?", (feed_id,))
            conn.commit()
        finally:
            conn.close()

    run_with_retry(_delete_feed)


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
        MAX(COALESCE(i.is_saved, 0)) as is_saved,
        MAX(COALESCE(i.saved_at, '')) as saved_at,
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

    for excluded_keyword in EXCLUDED_DOMAIN_KEYWORDS:
        query += " AND LOWER(COALESCE(i.link, '')) NOT LIKE ?"
        params.append(f"%{excluded_keyword}%")

    query += """
    GROUP BY i.link
    ORDER BY MAX(COALESCE(i.published, '')) DESC, MAX(i.id) DESC
    """

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def update_article_read_status(article_key_value, is_read):
    def _update_article_read_status():
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE items SET is_read=? WHERE article_key=?",
                (1 if is_read else 0, article_key_value)
            )
            conn.commit()
        finally:
            conn.close()

    run_with_retry(_update_article_read_status)


def update_article_saved_status(article_key_value, is_saved):
    now = datetime.now().isoformat(timespec="seconds")

    def _update_article_saved_status():
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                "UPDATE items SET is_saved=?, saved_at=? WHERE article_key=?",
                (1 if is_saved else 0, now if is_saved else None, article_key_value)
            )
            conn.commit()
        finally:
            conn.close()

    run_with_retry(_update_article_saved_status)


def update_articles_read_status(article_keys, is_read):
    keys = [key for key in article_keys if key]
    if not keys:
        return

    placeholders = ",".join(["?"] * len(keys))

    def _update_articles_read_status():
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                f"UPDATE items SET is_read=? WHERE article_key IN ({placeholders})",
                [1 if is_read else 0, *keys]
            )
            conn.commit()
        finally:
            conn.close()

    run_with_retry(_update_articles_read_status)
