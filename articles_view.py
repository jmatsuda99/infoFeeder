import streamlit as st

from article_utils import article_key, text_for_copy
from db import (
    list_articles,
    list_articles_by_key,
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


def initialize_article_filters(read_filter_options, saved_filter_options, sort_order_options):
    if "article_keyword" not in st.session_state:
        st.session_state.article_keyword = get_query_param("keyword", "")

    if "article_detail_count" not in st.session_state:
        st.session_state.article_detail_count = get_int_query_param("count", 100, min_value=1, max_value=100)

    if "article_read_filter" not in st.session_state:
        initial_read_filter = get_query_param("read", read_filter_options[0])
        st.session_state.article_read_filter = (
            initial_read_filter if initial_read_filter in read_filter_options else read_filter_options[0]
        )

    if "article_saved_filter" not in st.session_state:
        initial_saved_filter = get_query_param("saved", saved_filter_options[0])
        st.session_state.article_saved_filter = (
            initial_saved_filter if initial_saved_filter in saved_filter_options else saved_filter_options[0]
        )

    if "article_sort_order" not in st.session_state:
        initial_sort_order = get_query_param("sort", sort_order_options[0])
        st.session_state.article_sort_order = (
            initial_sort_order if initial_sort_order in sort_order_options else sort_order_options[0]
        )

    if "pending_read_changes" not in st.session_state:
        st.session_state.pending_read_changes = {}


def prepare_article_dataframe(keyword):
    df = list_articles(keyword)
    if df.empty:
        return df

    article_key_series = df["article_key"].fillna("").astype(str)
    missing_article_key = article_key_series.eq("")
    if missing_article_key.any():
        df.loc[missing_article_key, "article_key"] = df.loc[missing_article_key].apply(
            lambda row: article_key(row["title"], row["link"]),
            axis=1,
        )
    df["is_read"] = df["is_read"].fillna(0).astype(bool)
    df["is_saved"] = df["is_saved"].fillna(0).astype(bool)
    return df


def build_article_groups(df):
    grouped_rows = []

    for current_article_key, group_df in df.groupby("article_key", sort=False):
        sorted_group = group_df.sort_values(by=["published", "id"], ascending=[False, False]).copy()
        representative = sorted_group.iloc[0].copy()
        representative["article_key"] = current_article_key
        representative["is_read"] = bool(sorted_group["is_read"].any())
        representative["is_saved"] = bool(sorted_group["is_saved"].any())
        representative["group_count"] = int(len(sorted_group))
        grouped_rows.append(representative.to_dict())

    return df.__class__(grouped_rows)


def filter_articles(df, read_filter, saved_filter, read_filter_options, saved_filter_options):
    unread_filter = read_filter_options[0]
    read_done_filter = read_filter_options[1]
    saved_only_filter = saved_filter_options[1]

    if read_filter == unread_filter:
        filtered_df = df[df["is_read"] == False].copy()
    elif read_filter == read_done_filter:
        filtered_df = df[df["is_read"] == True].copy()
    else:
        filtered_df = df.copy()

    if saved_filter == saved_only_filter:
        filtered_df = filtered_df[filtered_df["is_saved"] == True].copy()

    return filtered_df


def sort_and_limit_articles(df, sort_order, detail_count, sort_order_options):
    oldest_first_sort = sort_order_options[1]
    saved_first_sort = sort_order_options[2]

    if sort_order == saved_first_sort:
        return df.sort_values(by=["is_saved", "published"], ascending=[False, False]).head(detail_count)
    if sort_order == oldest_first_sort:
        return df.sort_values(by="published", ascending=True).head(detail_count)
    return df.sort_values(by="published", ascending=False).head(detail_count)


def build_article_badges(row, is_read, is_saved, source_name):
    badge_html = (
        '<span class="if-badge">Read</span>'
        if is_read
        else '<span class="if-badge" style="background:#dbeafe;color:#163b63;">Unread</span>'
    )
    if is_saved:
        badge_html += '<span class="if-badge" style="background:#efe7c8;color:#6a5310;">Saved</span>'
    if source_name:
        badge_html += f'<span class="if-badge if-badge-muted">{source_name}</span>'
    if row["category"]:
        badge_html += f'<span class="if-badge if-badge-muted">{row["category"]}</span>'
    if int(row.get("group_count", 1)) > 1:
        badge_html += f'<span class="if-badge if-badge-muted">Grouped {int(row["group_count"])} items</span>'
    return badge_html


def get_pending_read_changes():
    return st.session_state.setdefault("pending_read_changes", {})


def get_effective_read_value(current_article_key, is_read):
    pending_read_changes = get_pending_read_changes()
    return pending_read_changes.get(current_article_key, is_read)


def render_article_toggles(item_id, current_article_key, is_read, is_saved):
    read_widget_key = f"read_{item_id}"
    effective_is_read = get_effective_read_value(current_article_key, is_read)
    if read_widget_key not in st.session_state:
        st.session_state[read_widget_key] = effective_is_read

    read_here = st.toggle("Read", key=read_widget_key)
    pending_read_changes = get_pending_read_changes()
    if read_here != is_read:
        pending_read_changes[current_article_key] = read_here
    else:
        pending_read_changes.pop(current_article_key, None)

    saved_here = st.toggle("Saved", value=is_saved, key=f"save_{item_id}")
    if saved_here != is_saved:
        update_article_saved_status(current_article_key, saved_here)
        get_related_articles.clear()
        st.rerun()


@st.cache_data(show_spinner=False)
def get_related_articles(article_key_value):
    related_articles = list_articles_by_key(article_key_value)
    if not related_articles:
        return []

    for related in related_articles:
        related["is_read"] = bool(related.get("is_read", 0))
        related["is_saved"] = bool(related.get("is_saved", 0))
    return related_articles


def render_article_detail(row, item_id, title, link):
    if row["link"]:
        link_col, copy_col = st.columns([6.5, 1.5])
        with link_col:
            st.markdown(f"**Link:** {row['link']}")
        with copy_col:
            render_copy_button(text_for_copy(title, link), f"{item_id}")

    summary_toggle = st.toggle("Show summary", value=False, key=f"show_summary_{item_id}")
    if summary_toggle:
        st.markdown("**Summary**")
        st.write(row["summary"] if row["summary"] else "No summary available.")

    related_toggle = st.toggle("Show related items", value=False, key=f"show_related_{item_id}")
    if related_toggle:
        related_articles = get_related_articles(row["article_key"])
        if len(related_articles) > 1:
            st.markdown("**Related items from the same primary source**")
            for index, related in enumerate(related_articles[:3], start=1):
                related_title = related["title"] if related["title"] else "(no title)"
                related_source = related["source_name"] if related["source_name"] else "-"
                related_link = related["link"] if related["link"] else ""
                related_published = format_jst_datetime(related["published"]) if related["published"] else ""
                st.markdown(f"{index}. `{related_source}` | {related_title}")
                if related_published:
                    st.caption(related_published)
                if related_link:
                    st.caption(related_link)
            remaining_count = len(related_articles) - 3
            if remaining_count > 0:
                st.caption(f"{remaining_count} more related items not shown.")
        else:
            st.caption("No additional related items.")


def render_article_card(row):
    title = row["title"] if row["title"] else "(no title)"
    published = row["published"] if row["published"] else ""
    published_display = format_jst_datetime(published)
    link = row["link"] if row["link"] else ""
    source_name = row["source_name"] if row["source_name"] else ""
    item_id = int(row["id"])
    current_article_key = row["article_key"]
    is_read = get_effective_read_value(current_article_key, bool(row["is_read"]))
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
                "Show details",
                value=False,
                key=f"show_detail_{item_id}",
            )

            if show_detail and not is_read:
                get_pending_read_changes()[current_article_key] = True
                st.session_state[f"read_{item_id}"] = True
                is_read = True

            if show_detail:
                render_article_detail(row, item_id, title, link)


def update_article_query_params(keyword, detail_count, read_filter, saved_filter, sort_order):
    st.query_params["keyword"] = keyword
    st.query_params["count"] = str(detail_count)
    st.query_params["read"] = read_filter
    st.query_params["saved"] = saved_filter
    st.query_params["sort"] = sort_order


def build_article_export_csv(visible_df):
    export_df = visible_df.copy()
    export_df["published_jst"] = export_df["published"].apply(format_jst_datetime)
    export_df["is_read"] = export_df["is_read"].map(lambda value: "yes" if bool(value) else "no")
    export_df["is_saved"] = export_df["is_saved"].map(lambda value: "yes" if bool(value) else "no")
    export_df["group_count"] = export_df["group_count"].fillna(1).astype(int)
    export_columns = [
        "title",
        "link",
        "source_name",
        "category",
        "published_jst",
        "is_read",
        "is_saved",
        "group_count",
        "summary",
    ]
    return export_df[export_columns].rename(
        columns={
            "source_name": "source",
            "group_count": "grouped_articles",
        }
    ).to_csv(index=False).encode("utf-8-sig")


def render_article_actions(unread_visible_keys, visible_df):
    pending_read_changes = get_pending_read_changes()
    action_col1, action_col2, action_col3 = st.columns([2, 2, 4])
    with action_col1:
        if unread_visible_keys and st.button("Mark visible groups as read", key="mark_visible_read"):
            pending_read_changes.update({article_key_value: True for article_key_value in unread_visible_keys})
            for _, row in visible_df.iterrows():
                if row["article_key"] in pending_read_changes:
                    st.session_state[f"read_{int(row['id'])}"] = True
    with action_col2:
        st.download_button(
            "Export CSV",
            data=build_article_export_csv(visible_df),
            file_name="articles_export.csv",
            mime="text/csv",
            key="download_articles_csv",
        )
    with action_col3:
        pending_count = len(pending_read_changes)
        apply_col, discard_col = st.columns([1.4, 1.2])
        with apply_col:
            if st.button(
                f"Apply Read Changes ({pending_count})",
                key="apply_read_changes",
                disabled=pending_count == 0,
            ):
                for article_key_value, read_value in pending_read_changes.items():
                    update_article_read_status(article_key_value, read_value)
                pending_read_changes.clear()
                get_related_articles.clear()
                for session_key in list(st.session_state.keys()):
                    if session_key.startswith("read_"):
                        del st.session_state[session_key]
                st.rerun()
        with discard_col:
            if st.button(
                "Discard Read Changes",
                key="discard_read_changes",
                disabled=pending_count == 0,
            ):
                pending_read_changes.clear()
                for session_key in list(st.session_state.keys()):
                    if session_key.startswith("read_"):
                        del st.session_state[session_key]
                st.rerun()


def render_articles_tab(read_filter_options, saved_filter_options, sort_order_options):
    st.subheader("Articles")

    with st.container(border=True):
        st.markdown('<div class="if-muted" style="margin-bottom:0.6rem;">Filters</div>', unsafe_allow_html=True)
        col1, col2, col3, col4, col5 = st.columns([3.0, 1.1, 1.2, 1.4, 1.3])

        with col1:
            keyword = st.text_input("Keyword", key="article_keyword")

        with col2:
            detail_count = st.number_input("Visible groups", min_value=1, max_value=100, key="article_detail_count")

        with col3:
            read_filter = st.selectbox("Read state", read_filter_options, key="article_read_filter")

        with col4:
            saved_filter = st.selectbox("Saved state", saved_filter_options, key="article_saved_filter")

        with col5:
            sort_order = st.selectbox("Sort order", sort_order_options, key="article_sort_order")
            st.markdown("<div style='height:0.2rem;'></div>", unsafe_allow_html=True)
            fetch_now = st.button("Fetch RSS now", key="fetch_articles_tab")

    update_article_query_params(keyword, detail_count, read_filter, saved_filter, sort_order)

    if fetch_now:
        fetch_articles_with_feedback("{count} new articles fetched.")

    df = prepare_article_dataframe(keyword)
    if df.empty:
        st.info("No articles found.")
        return

    grouped_df = build_article_groups(df)
    filtered_df = filter_articles(grouped_df, read_filter, saved_filter, read_filter_options, saved_filter_options)

    st.divider()
    st.subheader(f"Latest {detail_count} groups")

    visible_df = sort_and_limit_articles(filtered_df, sort_order, detail_count, sort_order_options)
    if visible_df.empty:
        st.info("No articles matched the current filters.")
        return

    unread_visible_keys = visible_df.loc[visible_df["is_read"] == False, "article_key"].dropna().unique().tolist()
    render_article_actions(unread_visible_keys, visible_df)

    for _, row in visible_df.iterrows():
        render_article_card(row)
