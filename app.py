
import sqlite3
import pandas as pd
import streamlit as st
from db import init_db, add_feed, list_feeds, update_feed_status, delete_feed
from fetcher import fetch_active_feeds

DB_PATH = "data/alerts.db"

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
            try:
                add_feed(name, url, category)
                st.success("追加しました")
            except Exception as e:
                st.error(str(e))

    st.divider()

    if st.button("RSS取得"):
        fetch_active_feeds()
        st.success("取得完了")

    feeds = list_feeds()

    for feed in feeds:
        feed_id, name, url, category, is_active, created_at, updated_at = feed

        col1, col2, col3 = st.columns([4,1,1])

        with col1:
            st.markdown(f"**{name}**")
            st.caption(url)

        with col2:
            active = st.checkbox("有効", value=bool(is_active), key=f"active_{feed_id}")

            if active != bool(is_active):
                update_feed_status(feed_id, active)
                st.rerun()

        with col3:
            if st.button("削除", key=f"delete_{feed_id}"):
                delete_feed(feed_id)
                st.rerun()


with tab2:
    conn = sqlite3.connect(DB_PATH)

    keyword = st.sidebar.text_input("検索")

    query = '''
    SELECT
        i.id,
        i.published,
        f.name as feed_name,
        i.title,
        i.link,
        i.summary
    FROM items i
    JOIN feeds f ON i.feed_id = f.id
    WHERE 1=1
    '''

    params = []

    if keyword:
        query += " AND (i.title LIKE ? OR i.summary LIKE ?)"
        like = f"%{keyword}%"
        params.extend([like, like])

    query += " ORDER BY i.published DESC"

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if df.empty:
        st.info("記事がありません")
    else:
        st.dataframe(
            df[["published","feed_name","title","link"]],
            use_container_width=True,
            hide_index=True
        )

        st.divider()
        st.subheader("記事詳細")

        for _, row in df.head(10).iterrows():
            with st.expander(f"{row['published']} | {row['title']}"):
                st.write(row["summary"])
                st.markdown(row["link"])
