import sqlite3
from pathlib import Path

DB_PATH = "data/alerts.db"

def get_conn():
    Path("data").mkdir(exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        feed_name TEXT,
        category TEXT,
        title TEXT,
        link TEXT UNIQUE,
        published TEXT,
        summary TEXT,
        fetched_at TEXT
    )
    """)

    conn.commit()
    conn.close()
