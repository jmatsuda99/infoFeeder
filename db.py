
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from article_utils import article_key
from exclusion_rules import DEFAULT_EXCLUDED_DOMAIN_NAMES, resolve_excluded_domain_keywords
from jst_format import is_recent_article
from policy_sources import COMMITTEE_WATCH_SOURCES, OFFICIAL_WATCH_SOURCES, POLICY_DESIGN_SOURCES

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "alerts.db"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_TIMEOUT_SECONDS = 30
DB_BUSY_TIMEOUT_MS = DB_TIMEOUT_SECONDS * 1000
DB_RETRY_ATTEMPTS = 5
DB_RETRY_DELAY_SECONDS = 0.4
def configure_conn(conn):
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {DB_BUSY_TIMEOUT_MS}")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.OperationalError:
        conn.execute("PRAGMA journal_mode = DELETE")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def is_retryable_error(error):
    msg = str(error).lower()
    # ロックだけでなく、スリープ復帰時に起きやすい I/O エラーやファイルオープン失敗もリトライ対象にする
    return "locked" in msg or "busy" in msg or "disk i/o error" in msg or "unable to open database file" in msg


def run_with_retry(action, *, retries=DB_RETRY_ATTEMPTS, delay=DB_RETRY_DELAY_SECONDS):
    last_error = None
    for attempt in range(retries):
        try:
            return action()
        except sqlite3.OperationalError as error:
            if not is_retryable_error(error):
                raise
            last_error = error
            if attempt == retries - 1:
                raise
            time.sleep(delay * (attempt + 1))
    raise last_error


def get_conn():
    def _connect():
        # ディレクトリ作成もリトライに含める（ドライブ未マウント対策）
        DATA_DIR.mkdir(exist_ok=True)
        return configure_conn(sqlite3.connect(str(DB_PATH), timeout=DB_TIMEOUT_SECONDS))

    return run_with_retry(_connect)

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

            cur.execute("""CREATE TABLE IF NOT EXISTS excluded_domains(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                created_at TEXT,
                updated_at TEXT
            )""")

            for default_name in DEFAULT_EXCLUDED_DOMAIN_NAMES:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO excluded_domains(name, created_at, updated_at)
                    VALUES(?,?,?)
                    """,
                    (default_name, datetime.now().isoformat(timespec="seconds"), datetime.now().isoformat(timespec="seconds"))
                )

            cur.execute("""CREATE TABLE IF NOT EXISTS items(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feed_id INTEGER,
                title TEXT,
                link TEXT UNIQUE,
                article_key TEXT,
                published TEXT,
                summary TEXT,
                generated_overview TEXT,
                generated_overview_error TEXT,
                generated_overview_source TEXT,
                generated_at TEXT,
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
            if "generated_overview" not in item_columns:
                cur.execute("ALTER TABLE items ADD COLUMN generated_overview TEXT")
            if "generated_overview_error" not in item_columns:
                cur.execute("ALTER TABLE items ADD COLUMN generated_overview_error TEXT")
            if "generated_overview_source" not in item_columns:
                cur.execute("ALTER TABLE items ADD COLUMN generated_overview_source TEXT")
            if "generated_at" not in item_columns:
                cur.execute("ALTER TABLE items ADD COLUMN generated_at TEXT")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_items_article_key ON items(article_key)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_items_published ON items(published)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_items_feed_id ON items(feed_id)")

            rows_to_refresh = cur.execute("""
                SELECT id, title, link, article_key
                FROM items
            """).fetchall()
            for row in rows_to_refresh:
                refreshed_article_key = article_key(row["title"], row["link"])
                if row["article_key"] == refreshed_article_key:
                    continue
                cur.execute(
                    "UPDATE items SET article_key=? WHERE id=?",
                    (refreshed_article_key, row["id"])
                )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS app_state(
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT
                )
                """
            )

            now = datetime.now().isoformat(timespec="seconds")
            for source in POLICY_DESIGN_SOURCES:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO feeds
                    (name, url, base_url, source_type, category, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, 'policy_listing', ?, 1, ?, ?)
                    """,
                    (source["name"], source["url"], source["url"], source["category"], now, now),
                )
                cur.execute(
                    """
                    UPDATE feeds
                    SET name=?, base_url=?, source_type='policy_listing', category=?, is_active=1, updated_at=?
                    WHERE url=? AND source_type != 'policy_listing'
                    """,
                    (source["name"], source["url"], source["category"], now, source["url"]),
                )

            for source in OFFICIAL_WATCH_SOURCES:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO feeds
                    (name, url, base_url, source_type, category, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, 'official_watch', ?, 1, ?, ?)
                    """,
                    (source["name"], source["url"], source["url"], source["category"], now, now),
                )

            for source in COMMITTEE_WATCH_SOURCES:
                cur.execute(
                    """
                    INSERT OR IGNORE INTO feeds
                    (name, url, base_url, source_type, category, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, 'committee_json', ?, 1, ?, ?)
                    """,
                    (source["name"], source["url"], source["site_url"], source["category"], now, now),
                )

            cur.execute("ANALYZE")
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


def list_excluded_domains():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM excluded_domains ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()
    return rows


def add_excluded_domain(name):
    normalized_name = (name or "").strip()
    if not normalized_name:
        return False

    now = datetime.now().isoformat(timespec="seconds")

    def _add_excluded_domain():
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO excluded_domains(name, created_at, updated_at)
                VALUES(?,?,?)
                """,
                (normalized_name, now, now),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    return run_with_retry(_add_excluded_domain)


def delete_excluded_domain(excluded_domain_id):
    def _delete_excluded_domain():
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("DELETE FROM excluded_domains WHERE id=?", (excluded_domain_id,))
            conn.commit()
        finally:
            conn.close()

    run_with_retry(_delete_excluded_domain)


def get_excluded_domain_names():
    return tuple(row["name"] for row in list_excluded_domains())


def get_excluded_domain_keywords():
    return resolve_excluded_domain_keywords(get_excluded_domain_names())


def get_app_state(key, default_value=""):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM app_state WHERE key=?", (key,))
    row = cur.fetchone()
    conn.close()
    if row is None:
        return default_value
    return row["value"]


def set_app_state(key, value):
    now = datetime.now().isoformat(timespec="seconds")

    def _set_app_state():
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO app_state(key, value, updated_at)
                VALUES(?,?,?)
                ON CONFLICT(key) DO UPDATE SET
                    value=excluded.value,
                    updated_at=excluded.updated_at
                """,
                (key, str(value), now),
            )
            conn.commit()
        finally:
            conn.close()

    run_with_retry(_set_app_state)


def get_summary_metrics_row():
    conn = get_conn()
    cur = conn.cursor()
    try:
        feed_metrics = cur.execute(
            """
            SELECT
                COUNT(*) AS total_sources,
                SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_sources,
                MAX(COALESCE(last_success_at, '')) AS latest_success_at,
                MAX(COALESCE(last_error_at, '')) AS latest_error_at,
                SUM(CASE WHEN COALESCE(last_error_at, '') != '' THEN 1 ELSE 0 END) AS error_feed_count
            FROM feeds
            """
        ).fetchone()

        unread_groups = pd.read_sql_query(
            """
            SELECT
                MAX(COALESCE(article_key, '')) AS article_key,
                MAX(COALESCE(published, '')) AS published,
                MAX(COALESCE(is_read, 0)) AS is_read
            FROM items
            WHERE COALESCE(article_key, '') != ''
            GROUP BY article_key
            """,
            conn,
        )
        if not unread_groups.empty:
            unread_groups = unread_groups[
                unread_groups["published"].apply(is_recent_article) & unread_groups["is_read"].fillna(0).eq(0)
            ]

        return {
            "total_sources": int(feed_metrics["total_sources"] or 0),
            "active_sources": int(feed_metrics["active_sources"] or 0),
            "latest_success_at": feed_metrics["latest_success_at"] or "",
            "latest_error_at": feed_metrics["latest_error_at"] or "",
            "error_feed_count": int(feed_metrics["error_feed_count"] or 0),
            "unread_articles": int(len(unread_groups.index)),
        }
    finally:
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
        MAX(COALESCE(i.is_saved, 0)) as is_saved,
        MAX(COALESCE(i.saved_at, '')) as saved_at,
        MAX(COALESCE(i.generated_overview, '')) as generated_overview,
        MAX(COALESCE(i.generated_overview_error, '')) as generated_overview_error,
        MAX(COALESCE(i.generated_overview_source, '')) as generated_overview_source,
        MAX(COALESCE(i.generated_at, '')) as generated_at,
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

    for excluded_keyword in get_excluded_domain_keywords():
        query += " AND LOWER(COALESCE(i.link, '')) NOT LIKE ?"
        params.append(f"%{excluded_keyword}%")

    query += """
    GROUP BY i.link
    ORDER BY MAX(COALESCE(i.published, '')) DESC, MAX(i.id) DESC
    """

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def get_item_with_feed_by_id(item_id):
    conn = get_conn()
    cur = conn.cursor()
    try:
        row = cur.execute(
            """
            SELECT
                i.id as id,
                i.published as published,
                COALESCE(f.category, '') as category,
                COALESCE(f.name, '') as source_name,
                COALESCE(i.article_key, '') as article_key,
                COALESCE(i.is_read, 0) as is_read,
                COALESCE(i.is_saved, 0) as is_saved,
                COALESCE(i.saved_at, '') as saved_at,
                COALESCE(i.generated_overview, '') as generated_overview,
                COALESCE(i.generated_overview_error, '') as generated_overview_error,
                COALESCE(i.generated_overview_source, '') as generated_overview_source,
                COALESCE(i.generated_at, '') as generated_at,
                i.link as link,
                COALESCE(i.title, '') as title,
                COALESCE(i.summary, '') as summary
            FROM items i
            JOIN feeds f ON i.feed_id = f.id
            WHERE i.id = ?
            """,
            (item_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_articles_by_key(article_key_value):
    conn = get_conn()
    cur = conn.cursor()
    try:
        rows = cur.execute(
            """
            SELECT
                i.id as id,
                i.published as published,
                COALESCE(f.category, '') as category,
                COALESCE(f.name, '') as source_name,
                COALESCE(i.article_key, '') as article_key,
                COALESCE(i.is_read, 0) as is_read,
                COALESCE(i.is_saved, 0) as is_saved,
                COALESCE(i.saved_at, '') as saved_at,
                COALESCE(i.generated_overview, '') as generated_overview,
                COALESCE(i.generated_overview_error, '') as generated_overview_error,
                COALESCE(i.generated_overview_source, '') as generated_overview_source,
                COALESCE(i.generated_at, '') as generated_at,
                i.link as link,
                COALESCE(i.title, '') as title,
                COALESCE(i.summary, '') as summary
            FROM items i
            JOIN feeds f ON i.feed_id = f.id
            WHERE COALESCE(i.article_key, '') = ?
            ORDER BY COALESCE(i.published, '') DESC, i.id DESC
            """,
            (article_key_value,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


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


def get_article_generation_input(article_key_value):
    conn = get_conn()
    cur = conn.cursor()
    try:
        row = cur.execute(
            """
            SELECT
                COALESCE(i.article_key, '') as article_key,
                COALESCE(i.title, '') as title,
                COALESCE(i.link, '') as link,
                COALESCE(i.summary, '') as summary,
                COALESCE(f.name, '') as source_name,
                COALESCE(f.category, '') as category
            FROM items i
            JOIN feeds f ON i.feed_id = f.id
            WHERE COALESCE(i.article_key, '') = ?
            ORDER BY COALESCE(i.published, '') DESC, i.id DESC
            LIMIT 1
            """,
            (article_key_value,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_article_generated_overview(article_key_value, overview_text, error_text="", source_text=""):
    now = datetime.now().isoformat(timespec="seconds")

    def _update_article_generated_overview():
        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                UPDATE items
                SET generated_overview=?, generated_overview_error=?, generated_overview_source=?, generated_at=?
                WHERE article_key=?
                """,
                (overview_text, error_text, source_text, now, article_key_value),
            )
            conn.commit()
        finally:
            conn.close()

    run_with_retry(_update_article_generated_overview)


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
