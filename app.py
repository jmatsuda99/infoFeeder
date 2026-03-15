import sqlite3
from urllib.parse import urlparse

import pandas as pd
import streamlit as st

from db import (
    add_feed,
    delete_feed,
    get_feed_by_id,
    init_db,
    list_categories,
    list_feeds,
    search_items,
    update_feed,
    update_feed_status,
)
from fetcher import fetch_active_feeds, validate_feed_url

DB_PATH = "data/alerts.db"

st.set_page_config(page_title="Google Alerts RSS Viewer", layout="wide")
st.title("Google Alerts RSS Viewer")
init_db()


def _safe_domain(url: str) -> str:
    try:
        return urlparse(url).netloc
    except Exception:
        return ""


def render_feed_manager() -> None:
    st.subheader("RSSフィード管理")

    with st.expander("RSS URLを追加", expanded=True):
        with st.form("add_feed_form", clear_on_submit=True):
            name = st.text_input("名前", placeholder="例: Battery Storage")
            url = st.text_input("RSS URL", placeholder="https://www.google.com/alerts/feeds/...")
            category = st.text_input("カテゴリ", placeholder="例: energy")
            submitted = st.form_submit_button("追加")

            if submitted:
                if not name.strip() or not url.strip():
                    st.error("名前とRSS URLは必須です。")
                else:
                    ok, message = validate_feed_url(url.strip())
                    if not ok:
                        st.error(f"RSS URLを確認できませんでした: {message}")
                    else:
                        try:
                            add_feed(name.strip(), url.strip(), category.strip())
                            st.success("RSSフィードを追加しました。")
                            st.rerun()
                        except sqlite3.IntegrityError:
                            st.error("このRSS URLはすでに登録済みです。")
                        except Exception as exc:
                            st.error(f"追加に失敗しました: {exc}")

    col_a, col_b = st.columns([1, 2])
    with col_a:
        if st.button("有効なRSSを取得", type="primary", use_container_width=True):
            with st.spinner("RSSを取得しています..."):
                result = fetch_active_feeds()
            st.success(
                f"取得完了: フィード {result['feeds_processed']}件 / 新規記事 {result['new_items']}件 / 失敗 {result['failed_feeds']}件"
            )
    with col_b:
        st.caption("Google Alerts の RSS URL を複数登録し、後から追加・編集・無効化できます。")

    feeds = list_feeds()
    if not feeds:
        st.info("まだRSSフィードが登録されていません。")
        return

    st.markdown("### 登録済みフィード")
    for feed in feeds:
        feed_id, name, url, category, is_active, last_checked_at, last_error, created_at, updated_at = feed
        with st.container(border=True):
            top1, top2, top3 = st.columns([5, 1, 1])
            with top1:
                st.markdown(f"**{name}**")
                meta = []
                if category:
                    meta.append(category)
                domain = _safe_domain(url)
                if domain:
                    meta.append(domain)
                if last_checked_at:
                    meta.append(f"last checked: {last_checked_at}")
                if meta:
                    st.caption(" | ".join(meta))
                st.code(url, language=None)
                if last_error:
                    st.warning(f"直近エラー: {last_error}")
            with top2:
                new_status = st.checkbox("有効", value=bool(is_active), key=f"active_{feed_id}")
                if new_status != bool(is_active):
                    update_feed_status(feed_id, new_status)
                    st.rerun()
            with top3:
                if st.button("削除", key=f"delete_{feed_id}", use_container_width=True):
                    delete_feed(feed_id)
                    st.rerun()

            with st.expander("編集"):
                current = get_feed_by_id(feed_id)
                with st.form(f"edit_feed_{feed_id}"):
                    new_name = st.text_input("名前", value=current[1])
                    new_url = st.text_input("RSS URL", value=current[2])
                    new_category = st.text_input("カテゴリ", value=current[3] or "")
                    save = st.form_submit_button("保存")
                    if save:
                        if not new_name.strip() or not new_url.strip():
                            st.error("名前とRSS URLは必須です。")
                        else:
                            ok, message = validate_feed_url(new_url.strip())
                            if not ok:
                                st.error(f"RSS URLを確認できませんでした: {message}")
                            else:
                                try:
                                    update_feed(feed_id, new_name.strip(), new_url.strip(), new_category.strip())
                                    st.success("更新しました。")
                                    st.rerun()
                                except sqlite3.IntegrityError:
                                    st.error("同じRSS URLがすでに登録されています。")
                                except Exception as exc:
                                    st.error(f"更新に失敗しました: {exc}")


def render_item_view() -> None:
    st.subheader("記事一覧")
    with st.sidebar:
        st.header("絞り込み")
        keyword = st.text_input("キーワード")
        category_options = ["すべて"] + list_categories()
        category = st.selectbox("カテゴリ", category_options, index=0)
        feeds_df = pd.DataFrame(list_feeds(), columns=[
            "id", "name", "url", "category", "is_active", "last_checked_at", "last_error", "created_at", "updated_at"
        ])
        feed_names = ["すべて"] + (feeds_df["name"].tolist() if not feeds_df.empty else [])
        feed_name = st.selectbox("フィード", feed_names, index=0)
        only_active = st.checkbox("有効フィードのみ", value=True)
        limit = st.slider("表示件数", min_value=20, max_value=500, value=100, step=20)

    selected_category = None if category == "すべて" else category
    selected_feed_name = None if feed_name == "すべて" else feed_name

    df = search_items(
        keyword=keyword.strip(),
        category=selected_category,
        feed_name=selected_feed_name,
        only_active=only_active,
        limit=limit,
    )

    if df.empty:
        st.info("条件に一致する記事はありません。")
        return

    show_df = df[["published", "feed_name", "category", "title", "domain", "link"]].copy()
    st.dataframe(show_df, use_container_width=True, hide_index=True)

    st.markdown("### 詳細")
    idx = st.number_input("詳細表示 index", min_value=0, max_value=len(df) - 1, value=0, step=1)
    row = df.iloc[int(idx)]
    st.markdown(f"**{row['title']}**")
    meta = [str(row["published"] or "")]
    if row["feed_name"]:
        meta.append(str(row["feed_name"]))
    if row["category"]:
        meta.append(str(row["category"]))
    if row["domain"]:
        meta.append(str(row["domain"]))
    st.caption(" | ".join([m for m in meta if m]))
    st.link_button("記事を開く", str(row["link"]))
    if row["summary"]:
        st.markdown(row["summary"], unsafe_allow_html=True)


def main() -> None:
    tab1, tab2 = st.tabs(["RSS管理", "記事一覧"])
    with tab1:
        render_feed_manager()
    with tab2:
        render_item_view()


if __name__ == "__main__":
    main()
