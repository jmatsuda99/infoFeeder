
import sqlite3
import pandas as pd
import streamlit as st

from db import init_db, add_feed, list_feeds, update_feed_status, delete_feed
from fetcher import fetch_active_feeds

DB_PATH = "data/alerts.db"

st.set_page_config(page_title="Google Alerts RSS Viewer", layout="wide")
st.title("Google Alerts RSS Viewer")

init_db()

def parse_google_alert_urls(text):
    urls = []
    for line in text.splitlines():
        value = line.strip()
        if not value:
            continue
        if value.startswith("http://") or value.startswith("https://"):
            urls.append(value)
    return urls

if "hidden_links" not in st.session_state:
    st.session_state.hidden_links = set()

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
                created = add_feed(name.strip(), url.strip(), category.strip())
                if created:
                    st.success("追加しました")
                    st.rerun()
                else:
                    st.warning("同じRSS URLはすでに登録済みです")

    st.caption("GoogleアラートのRSS URLもそのまま登録できます")

    with st.form("bulk_google_alert_form"):
        bulk_name_prefix = st.text_input("一括追加時の名前プレフィックス", value="Google Alert")
        bulk_category = st.text_input("一括追加時のカテゴリ", key="bulk_category")
        bulk_urls = st.text_area(
            "GoogleアラートRSS URL一覧",
            help="Googleアラート管理画面でRSSリンクをコピーし、1行に1件ずつ貼り付けてください"
        )
        bulk_submitted = st.form_submit_button("GoogleアラートRSSを一括追加")

        if bulk_submitted:
            urls = parse_google_alert_urls(bulk_urls)
            if not urls:
                st.error("RSS URLを1件以上入力してください")
            else:
                added_count = 0
                skipped_count = 0

                for index, feed_url in enumerate(urls, start=1):
                    feed_name = f"{bulk_name_prefix.strip() or 'Google Alert'} {index}"
                    created = add_feed(feed_name, feed_url, bulk_category.strip())
                    if created:
                        added_count += 1
                    else:
                        skipped_count += 1

                if added_count:
                    st.success(f"{added_count}件のRSSを追加しました")
                if skipped_count:
                    st.info(f"{skipped_count}件は重複のため追加しませんでした")
                if added_count:
                    st.rerun()

    st.divider()

    if st.button("RSS取得"):
        count = fetch_active_feeds()
        st.success(f"{count}件の新規記事を取得")

    feeds = list_feeds()

    if feeds:
        for feed in feeds:
            feed_id = feed["id"]
            name = feed["name"] or ""
            url = feed["url"] or ""
            category = feed["category"] or ""
            is_active = feed["is_active"] or 0

            col1, col2, col3 = st.columns([5,1,1])

            with col1:
                st.markdown(f"**{name}**")
                caption = url if not category else f"{category} | {url}"
                st.caption(caption)

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

    st.subheader("記事一覧")

    col1, col2 = st.columns([3,1])

    with col1:
        keyword = st.text_input("検索")

    with col2:
        detail_count = st.number_input("詳細表示件数", min_value=1, max_value=100, value=100)

    query = """
    SELECT
        MAX(i.id) as id,
        MAX(i.published) as published,
        MAX(COALESCE(f.category,'')) as category,
        i.link as link,
        MAX(i.title) as title,
        MAX(COALESCE(i.summary,'')) as summary
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
    ORDER BY MAX(COALESCE(i.published,'')) DESC, MAX(i.id) DESC
    """

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if df.empty:
        st.info("記事がありません")
    else:
        display_df = df[["published","category","title","link"]].copy()
        display_df.insert(
            0,
            "非表示",
            display_df["link"].apply(lambda x: x in st.session_state.hidden_links)
        )

        edited_df = st.data_editor(
            display_df,
            use_container_width=True,
            hide_index=True,
            disabled=["published","category","title","link"],
            key="list_editor"
        )

        list_hidden_links = set(
            edited_df.loc[edited_df["非表示"] == True, "link"].tolist()
        )
        st.session_state.hidden_links = list_hidden_links

        st.divider()
        st.subheader(f"詳細表示（最新 {detail_count} 件）")

        visible_df = df[~df["link"].isin(st.session_state.hidden_links)].copy()
        visible_df = visible_df.sort_values(by="published", ascending=False).head(detail_count)

        if visible_df.empty:
            st.info("詳細表示対象の記事がありません")
        else:
            for _, row in visible_df.iterrows():
                title = row["title"] if row["title"] else "(no title)"
                published = row["published"] if row["published"] else ""
                link = row["link"] if row["link"] else ""

                exp_col1, exp_col2 = st.columns([8, 1])
                with exp_col2:
                    hidden_here = st.checkbox(
                        "非表示",
                        value=(link in st.session_state.hidden_links),
                        key=f"detail_hide_{link}"
                    )
                    if hidden_here and link not in st.session_state.hidden_links:
                        st.session_state.hidden_links.add(link)
                        st.rerun()
                    if (not hidden_here) and (link in st.session_state.hidden_links):
                        st.session_state.hidden_links.remove(link)
                        st.rerun()

                with exp_col1:
                    with st.expander(f"{published} | {title}", expanded=False):
                        if row["category"]:
                            st.markdown(f"**Category:** {row['category']}")
                        if row["link"]:
                            st.markdown(f"**Link:** {row['link']}")
                        st.markdown("**Summary**")
                        st.write(row["summary"] if row["summary"] else "要約なし")
