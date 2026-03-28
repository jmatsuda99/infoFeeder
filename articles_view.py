import streamlit as st

from article_utils import article_key, deduplicate_articles, text_for_copy
from db import (
    list_articles,
    update_article_read_status,
    update_article_saved_status,
    update_articles_read_status,
)
from ui_common import fetch_articles_with_feedback, format_jst_datetime, render_copy_button


def get_query_param(name, default=""):
    value = st.query_params.get(name, default)
    if isinstance(value, list):
        return value[0] if value else default
    return value


def get_int_query_param(name, default, min_value=None, max_value=None):
    value = get_query_param(name, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default

    if min_value is not None:
        parsed = max(min_value, parsed)
    if max_value is not None:
        parsed = min(max_value, parsed)
    return parsed


def initialize_article_filters(read_filter_options, sort_order_options):
    if "article_keyword" not in st.session_state:
        st.session_state.article_keyword = get_query_param("keyword", "")

    if "article_detail_count" not in st.session_state:
        st.session_state.article_detail_count = get_int_query_param("count", 100, min_value=1, max_value=100)

    if "article_read_filter" not in st.session_state:
        initial_read_filter = get_query_param("read", read_filter_options[0])
        st.session_state.article_read_filter = (
            initial_read_filter if initial_read_filter in read_filter_options else read_filter_options[0]
        )

    if "article_sort_order" not in st.session_state:
        initial_sort_order = get_query_param("sort", sort_order_options[0])
        st.session_state.article_sort_order = (
            initial_sort_order if initial_sort_order in sort_order_options else sort_order_options[0]
        )


def prepare_article_dataframe(keyword):
    df = list_articles(keyword)
    if df.empty:
        return df

    df["article_key"] = df["article_key"].where(
        df["article_key"].notna() & (df["article_key"] != ""),
        df.apply(lambda row: article_key(row["title"], row["link"]), axis=1),
    )
    df["is_read"] = df["is_read"].fillna(0).astype(bool)
    df["is_saved"] = df["is_saved"].fillna(0).astype(bool)
    return deduplicate_articles(df)


def filter_articles(df, read_filter):
    if read_filter == "未読":
        return df[df["is_read"] == False].copy()
    if read_filter == "既読":
        return df[df["is_read"] == True].copy()
    return df.copy()


def sort_and_limit_articles(df, sort_order, detail_count):
    if sort_order == "保存記事を先頭":
        return df.sort_values(by=["is_saved", "published"], ascending=[False, False]).head(detail_count)
    if sort_order == "古い順":
        return df.sort_values(by="published", ascending=True).head(detail_count)
    return df.sort_values(by="published", ascending=False).head(detail_count)


def build_article_badges(row, is_read, is_saved, source_name):
    badge_html = (
        '<span class="if-badge">既読</span>'
        if is_read
        else '<span class="if-badge" style="background:#dbeafe;color:#163b63;">未読</span>'
    )
    if is_saved:
        badge_html += '<span class="if-badge" style="background:#efe7c8;color:#6a5310;">保存</span>'
    if source_name:
        badge_html += f'<span class="if-badge if-badge-muted">{source_name}</span>'
    if row["category"]:
        badge_html += f'<span class="if-badge if-badge-muted">{row["category"]}</span>'
    return badge_html


def render_article_toggles(item_id, current_article_key, is_read, is_saved):
    read_here = st.toggle("既読", value=is_read, key=f"read_{item_id}")
    if read_here != is_read:
        update_article_read_status(current_article_key, read_here)
        st.rerun()

    saved_here = st.toggle("保存", value=is_saved, key=f"save_{item_id}")
    if saved_here != is_saved:
        update_article_saved_status(current_article_key, saved_here)
        st.rerun()


def render_article_detail(row, item_id, title, link):
    if row["link"]:
        link_col, copy_col = st.columns([6.5, 1.5])
        with link_col:
            st.markdown(f"**リンク:** {row['link']}")
        with copy_col:
            render_copy_button(text_for_copy(title, link), f"{item_id}")
    st.markdown("**要約**")
    st.write(row["summary"] if row["summary"] else "要約はありません。")


def render_article_card(row):
    title = row["title"] if row["title"] else "(no title)"
    published = row["published"] if row["published"] else ""
    published_display = format_jst_datetime(published)
    link = row["link"] if row["link"] else ""
    source_name = row["source_name"] if row["source_name"] else ""
    item_id = int(row["id"])
    current_article_key = row["article_key"]
    is_read = bool(row["is_read"])
    is_saved = bool(row["is_saved"])

    with st.container(border=True):
        badge_html = build_article_badges(row, is_read, is_saved, source_name)
        st.markdown(badge_html, unsafe_allow_html=True)
        exp_col1, exp_col2 = st.columns([1.2, 8])

        with exp_col1:
            render_article_toggles(item_id, current_article_key, is_read, is_saved)

        with exp_col2:
            st.markdown(f'<div class="if-card-title">{title}</div>', unsafe_allow_html=True)
            if published_display:
                st.markdown(f'<div class="if-muted">{published_display}</div>', unsafe_allow_html=True)
            show_detail = st.toggle(
                "詳細を表示",
                value=False,
                key=f"show_detail_{item_id}",
            )

            if show_detail and not is_read:
                update_article_read_status(current_article_key, True)
                is_read = True

            if show_detail:
                render_article_detail(row, item_id, title, link)


def update_article_query_params(keyword, detail_count, read_filter, sort_order):
    st.query_params["keyword"] = keyword
    st.query_params["count"] = str(detail_count)
    st.query_params["read"] = read_filter
    st.query_params["sort"] = sort_order


def build_article_export_csv(visible_df):
    export_df = visible_df.copy()
    export_df["published_jst"] = export_df["published"].apply(format_jst_datetime)
    export_df["is_read"] = export_df["is_read"].map(lambda value: "yes" if bool(value) else "no")
    export_df["is_saved"] = export_df["is_saved"].map(lambda value: "yes" if bool(value) else "no")
    export_columns = [
        "title",
        "link",
        "source_name",
        "category",
        "published_jst",
        "is_read",
        "is_saved",
        "summary",
    ]
    return export_df[export_columns].rename(
        columns={
            "source_name": "source",
        }
    ).to_csv(index=False).encode("utf-8-sig")


def render_article_actions(unread_visible_keys, visible_df):
    action_col1, action_col2, action_col3 = st.columns([2, 2, 4])
    with action_col1:
        if unread_visible_keys and st.button("表示中をすべて既読", key="mark_visible_read"):
            update_articles_read_status(unread_visible_keys, True)
            st.rerun()
    with action_col2:
        st.download_button(
            "CSV出力",
            data=build_article_export_csv(visible_df),
            file_name="articles_export.csv",
            mime="text/csv",
            key="download_articles_csv",
        )


def render_articles_tab(read_filter_options, sort_order_options):
    st.subheader("記事一覧")

    with st.container(border=True):
        st.markdown('<div class="if-muted" style="margin-bottom:0.6rem;">表示条件</div>', unsafe_allow_html=True)
        col1, col2, col3, col4 = st.columns([3.2, 1.2, 1.4, 1.3])

        with col1:
            keyword = st.text_input("キーワード", key="article_keyword")

        with col2:
            detail_count = st.number_input("表示件数", min_value=1, max_value=100, key="article_detail_count")

        with col3:
            read_filter = st.selectbox("表示", read_filter_options, key="article_read_filter")

        with col4:
            sort_order = st.selectbox("並び順", sort_order_options, key="article_sort_order")
            st.markdown("<div style='height:0.2rem;'></div>", unsafe_allow_html=True)
            fetch_now = st.button("RSS取得", key="fetch_articles_tab")

    update_article_query_params(keyword, detail_count, read_filter, sort_order)

    if fetch_now:
        fetch_articles_with_feedback("{count} 件の新着記事を取得しました。")

    df = prepare_article_dataframe(keyword)
    if df.empty:
        st.info("記事がありません。")
        return

    filtered_df = filter_articles(df, read_filter)

    st.divider()
    st.subheader(f"最新 {detail_count} 件")

    visible_df = sort_and_limit_articles(filtered_df, sort_order, detail_count)
    if visible_df.empty:
        st.info("条件に合う記事がありません。")
        return

    unread_visible_keys = visible_df.loc[visible_df["is_read"] == False, "article_key"].dropna().tolist()
    render_article_actions(unread_visible_keys, visible_df)

    for _, row in visible_df.iterrows():
        render_article_card(row)
