import json

import streamlit as st
import streamlit.components.v1 as components

from article_utils import (
    article_key,
    deduplicate_articles,
    parse_google_alert_urls,
    text_for_copy,
    unique_urls,
)
from db import (
    add_feed,
    delete_feed,
    init_db,
    list_articles,
    list_feeds,
    update_feed_status,
)
from fetcher import fetch_active_feeds


st.set_page_config(page_title="Google Alerts RSS Viewer", layout="wide")
st.title("Google Alerts RSS Viewer")

init_db()

if "read_article_keys" not in st.session_state:
    st.session_state.read_article_keys = set()


def render_copy_button(copy_text, key):
    button_id = f"copy-button-{key}"
    payload = json.dumps(copy_text)
    html_block = f"""
    <button id="{button_id}" style="
        background:#f3f4f6;
        border:1px solid #d1d5db;
        border-radius:6px;
        padding:0.35rem 0.75rem;
        cursor:pointer;
        font-size:0.9rem;
    ">コピー</button>
    <script>
    const button = document.getElementById("{button_id}");
    if (button) {{
        button.onclick = async () => {{
            try {{
                await navigator.clipboard.writeText({payload});
                const original = button.innerText;
                button.innerText = "コピー済み";
                setTimeout(() => button.innerText = original, 1200);
            }} catch (error) {{
                button.innerText = "失敗";
            }}
        }};
    }}
    </script>
    """
    components.html(html_block, height=40)


def add_urls_as_feeds(urls, name_prefix, category):
    added_count = 0
    skipped_count = 0

    for index, feed_url in enumerate(urls, start=1):
        feed_name = f"{name_prefix or 'Google Alert'} {index}"
        created = add_feed(feed_name, feed_url, category)
        if created:
            added_count += 1
        else:
            skipped_count += 1

    return added_count, skipped_count


tab1, tab2 = st.tabs(["RSS登録", "記事一覧"])

with tab1:
    st.subheader("RSS URL登録")

    with st.form("add_feed_form"):
        name = st.text_input("名前")
        url = st.text_input("RSS URL")
        category = st.text_input("カテゴリ")
        submitted = st.form_submit_button("追加")

        if submitted:
            if not name.strip() or not url.strip():
                st.error("名前とRSS URLを入力してください")
            else:
                created = add_feed(name.strip(), url.strip(), category.strip())
                if created:
                    st.success("追加しました")
                    st.rerun()
                else:
                    st.warning("そのRSS URLはすでに登録されています")

    st.caption("GoogleアラートのRSS URLもそのまま登録できます")
    st.info("Google Alerts RSS URLs can be pasted in bulk below. Paste one URL per line.")

    with st.form("bulk_google_alert_form"):
        bulk_name_prefix = st.text_input("一括追加時の名前プレフィックス", value="Google Alert")
        bulk_category = st.text_input("一括追加時のカテゴリ", key="bulk_category")
        bulk_urls = st.text_area(
            "GoogleアラートのRSS URL一覧",
            help="Googleアラート管理画面のRSSリンクを、1行につき1件ずつ貼り付けてください。"
        )
        bulk_submitted = st.form_submit_button("GoogleアラートRSSを一括追加")

        if bulk_submitted:
            urls = parse_google_alert_urls(bulk_urls)
            deduped_urls = unique_urls(urls)
            duplicate_count = len(urls) - len(deduped_urls)

            if not deduped_urls:
                st.error("RSS URLを1件以上入力してください")
            else:
                added_count, skipped_count = add_urls_as_feeds(
                    deduped_urls,
                    bulk_name_prefix.strip(),
                    bulk_category.strip()
                )

                st.info(f"Parsed {len(urls)} URLs, using {len(deduped_urls)} unique URLs.")
                if duplicate_count:
                    st.info(f"Ignored {duplicate_count} duplicate URLs in the pasted list.")
                if added_count:
                    st.success(f"{added_count}件のRSSを追加しました")
                if skipped_count:
                    st.info(f"{skipped_count}件は既存URLのため追加しませんでした")
                if added_count:
                    st.rerun()

    st.divider()

    if st.button("RSS取得"):
        count = fetch_active_feeds()
        st.success(f"{count}件の新着記事を取得しました")

    feeds = list_feeds()

    if feeds:
        for feed in feeds:
            feed_id = feed["id"]
            name = feed["name"] or ""
            url = feed["url"] or ""
            category = feed["category"] or ""
            is_active = feed["is_active"] or 0

            col1, col2, col3 = st.columns([5, 1, 1])

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

    st.subheader("記事一覧")

    col1, col2, col3 = st.columns([3, 1, 1.2])

    with col1:
        keyword = st.text_input("キーワード")

    with col2:
        detail_count = st.number_input("表示件数", min_value=1, max_value=100, value=100)

    with col3:
        read_filter = st.selectbox("表示", ["未読", "既読", "すべて"], index=0)

    if st.button("Fetch RSS", key="fetch_articles_tab"):
        count = fetch_active_feeds()
        st.success(f"Fetched {count} new articles")

    df = list_articles(keyword)

    if df.empty:
        st.info("記事がありません")
    else:
        df["article_key"] = df.apply(
            lambda row: article_key(row["title"], row["link"]),
            axis=1
        )
        df["is_read"] = df["article_key"].apply(
            lambda key: key in st.session_state.read_article_keys
        )
        df = deduplicate_articles(df)

        if read_filter == "未読":
            filtered_df = df[df["is_read"] == False].copy()
        elif read_filter == "既読":
            filtered_df = df[df["is_read"] == True].copy()
        else:
            filtered_df = df.copy()

        st.divider()
        st.subheader(f"詳細表示（最新 {detail_count} 件）")

        visible_df = filtered_df.sort_values(by="published", ascending=False).head(detail_count)

        if visible_df.empty:
            st.info("該当する記事はありません")
        else:
            for _, row in visible_df.iterrows():
                title = row["title"] if row["title"] else "(no title)"
                published = row["published"] if row["published"] else ""
                link = row["link"] if row["link"] else ""
                item_id = int(row["id"])
                current_article_key = row["article_key"]
                is_read = bool(row["is_read"])

                exp_col1, exp_col2 = st.columns([1.2, 8])

                with exp_col1:
                    read_here = st.checkbox("既読", value=is_read, key=f"read_{item_id}")
                    if read_here != is_read:
                        if read_here:
                            st.session_state.read_article_keys.add(current_article_key)
                        else:
                            st.session_state.read_article_keys.discard(current_article_key)
                        st.rerun()

                with exp_col2:
                    show_detail = st.toggle(
                        f"{published} | {title}",
                        value=False,
                        key=f"show_detail_{item_id}"
                    )

                    if show_detail and not is_read:
                        st.session_state.read_article_keys.add(current_article_key)
                        is_read = True

                    if show_detail:
                        if row["category"]:
                            st.markdown(f"**Category:** {row['category']}")
                        if row["link"]:
                            st.markdown(f"**Link:** {row['link']}")
                            render_copy_button(text_for_copy(title, link), f"{item_id}")
                        st.markdown("**Summary**")
                        st.write(row["summary"] if row["summary"] else "要約なし")
