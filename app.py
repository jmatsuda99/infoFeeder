import json
import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

from db import init_db
from fetcher import fetch_active_feeds

DB_PATH = "data/alerts.db"
FEEDS_PATH = "feeds.json"


def load_feeds():
    path = Path(FEEDS_PATH)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_feeds(feeds):
    Path(FEEDS_PATH).write_text(
        json.dumps(feeds, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def add_feed(name, url, category=""):
    feeds = load_feeds()
    for feed in feeds:
        if feed.get("url", "").strip() == url.strip():
            raise ValueError("同じURLのRSSはすでに登録されています")
    feeds.append({
        "name": name.strip(),
        "url": url.strip(),
        "category": category.strip(),
        "is_active": True
    })
    save_feeds(feeds)


def update_feed_status(index, is_active):
    feeds = load_feeds()
    feeds[index]["is_active"] = bool(is_active)
    save_feeds(feeds)


def delete_feed(index):
    feeds = load_feeds()
    del feeds[index]
    save_feeds(feeds)


st.set_page_config(page_title="Google Alerts RSS Viewer", layout="wide")
st.title("Google Alerts RSS Viewer")

init_db()

tab1, tab2 = st.tabs(["RSS管理", "記事一覧"])

with tab1:
    st.subheader("RSS URL追加")

    with st.form("add_feed_form"):
        name = st.text_input("名前")
        url = st.text_input("RSS URL")
        category = st.text_input("カテゴリ")
        submitted = st.form_submit_button("追加")

        if submitted:
            if not name.strip() or not url.strip():
                st.error("名前とRSS URLは必須です")
            else:
                try:
                    add_feed(name, url, category)
                    st.success("追加しました")
                    st.rerun()
                except Exception as e:
                    st.error(f"追加失敗: {e}")

    st.divider()

    col_a, col_b = st.columns([1, 2])
    with col_a:
        if st.button("RSS取得"):
            try:
                count = fetch_active_feeds()
                st.success(f"取得完了: {count}件の新規記事を保存")
            except Exception as e:
                st.error(f"取得失敗: {e}")
    with col_b:
        st.caption("GitHub Actions も feeds.json を参照します。定期取得と同じ設定を使うには、このファイルをGitHubへ commit してください。")

    feeds = load_feeds()

    if not feeds:
        st.info("登録済みRSSはありません")
    else:
        for i, feed in enumerate(feeds):
            name = feed.get("name", "")
            url = feed.get("url", "")
            category = feed.get("category", "")
            is_active = bool(feed.get("is_active", True))

            col1, col2, col3 = st.columns([5, 1, 1])

            with col1:
                st.markdown(f"**{name}**")
                caption = url if not category else f"{category} | {url}"
                st.caption(caption)

            with col2:
                active = st.checkbox("有効", value=is_active, key=f"active_{i}")
                if active != is_active:
                    update_feed_status(i, active)
                    st.rerun()

            with col3:
                if st.button("削除", key=f"delete_{i}"):
                    delete_feed(i)
                    st.rerun()

    st.divider()
    st.subheader("feeds.json")
    st.code(Path(FEEDS_PATH).read_text(encoding="utf-8") if Path(FEEDS_PATH).exists() else "[]", language="json")
    st.caption("定期取得に反映させるには、この feeds.json を GitHub リポジトリ側にも反映してください。")

with tab2:
    conn = sqlite3.connect(DB_PATH)

    st.subheader("記事一覧")

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        keyword = st.text_input("検索")
    with col2:
        feed_filter = st.text_input("フィード名で絞り込み")
    with col3:
        detail_count = st.number_input("詳細表示件数", min_value=1, max_value=50, value=10, step=1)

    query = """
    SELECT
        MAX(i.id) as id,
        MAX(i.published) as published,
        MAX(i.feed_name) as feed_name,
        MAX(COALESCE(i.category, '')) as category,
        i.link as link,
        MAX(i.title) as title,
        MAX(COALESCE(i.summary, '')) as summary
    FROM items i
    WHERE 1=1
    """
    params = []

    if keyword:
        query += " AND (i.title LIKE ? OR i.summary LIKE ?)"
        like = f"%{keyword}%"
        params.extend([like, like])

    if feed_filter:
        query += " AND i.feed_name LIKE ?"
        params.append(f"%{feed_filter}%")

    query += """
    GROUP BY i.link
    ORDER BY MAX(COALESCE(i.published, '')) DESC, MAX(i.id) DESC
    """

    try:
        df = pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()

    if df.empty:
        st.info("記事がありません")
    else:
        st.dataframe(
            df[["published", "feed_name", "category", "title", "link"]],
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        st.subheader(f"詳細表示（先頭 {detail_count} 件）")

        detail_df = df.head(detail_count)
        for _, row in detail_df.iterrows():
            title = row["title"] if row["title"] else "(no title)"
            published = row["published"] if row["published"] else ""
            feed_name = row["feed_name"] if row["feed_name"] else ""

            with st.expander(f"{published} | {feed_name} | {title}", expanded=False):
                if row["category"]:
                    st.markdown(f"**Category**: {row['category']}")
                if row["published"]:
                    st.markdown(f"**Published**: {row['published']}")
                if row["link"]:
                    st.markdown(f"**Link**: {row['link']}")
                st.markdown("**Summary**")
                st.write(row["summary"] if row["summary"] else "要約なし")
