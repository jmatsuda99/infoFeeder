import json
from datetime import datetime, timedelta

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
    update_article_read_status,
    update_feed_status,
)
from fetcher import discover_feed_source, fetch_active_feeds


st.set_page_config(page_title="Google Alerts RSS Viewer", layout="wide")
st.title("Google Alerts RSS Viewer")

init_db()

TAB_SOURCE_SETUP = "Source Setup"
TAB_ARTICLES = "Articles"
TAB_OPTIONS = [TAB_SOURCE_SETUP, TAB_ARTICLES]


def get_next_half_hour(now):
    next_half_hour = now.replace(second=0, microsecond=0)
    if now.minute < 30:
        next_half_hour = next_half_hour.replace(minute=30)
    else:
        next_half_hour = (next_half_hour + timedelta(hours=1)).replace(minute=0)
    return next_half_hour


def schedule_page_refresh():
    now = datetime.now()
    next_half_hour = get_next_half_hour(now)
    delay_ms = max(1000, int((next_half_hour - now).total_seconds() * 1000) + 250)
    html_block = f"""
    <script>
    setTimeout(() => {{
        window.parent.location.reload();
    }}, {delay_ms});
    </script>
    """
    components.html(html_block, height=0)


def run_scheduled_fetch():
    now = datetime.now()
    current_slot = None

    if now.minute in (0, 30):
        current_slot = now.strftime("%Y-%m-%d %H:%M")

    if current_slot and st.session_state.get("last_auto_fetch_slot") != current_slot:
        count = fetch_active_feeds()
        st.session_state.last_auto_fetch_slot = current_slot
        st.session_state.auto_fetch_message = (
            f"Auto-fetched {count} new articles at {now.strftime('%Y-%m-%d %H:%M:%S')}."
        )

    if not current_slot and st.session_state.get("last_auto_fetch_slot"):
        last_slot = st.session_state["last_auto_fetch_slot"]
        if last_slot[:14] != now.strftime("%Y-%m-%d %H:"):
            st.session_state.last_auto_fetch_slot = None

    return get_next_half_hour(now)


next_auto_fetch_at = run_scheduled_fetch()
schedule_page_refresh()

if st.session_state.get("auto_fetch_message"):
    st.caption(st.session_state["auto_fetch_message"])

st.caption(f"Next auto fetch: {next_auto_fetch_at.strftime('%Y-%m-%d %H:%M')}")


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
    ">Copy</button>
    <script>
    const button = document.getElementById("{button_id}");
    if (button) {{
        button.onclick = async () => {{
            try {{
                await navigator.clipboard.writeText({payload});
                const original = button.innerText;
                button.innerText = "Copied";
                setTimeout(() => button.innerText = original, 1200);
            }} catch (error) {{
                button.innerText = "Failed";
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


def add_source_from_base_url(name, base_url, category):
    detected = discover_feed_source(base_url)
    created = add_feed(
        name,
        detected["fetch_url"],
        category,
        source_type=detected["source_type"],
        base_url=detected["base_url"],
    )
    return created, detected


def sync_selected_tab():
    selected_tab = st.session_state.get("main_tabs", TAB_SOURCE_SETUP)
    if selected_tab in TAB_OPTIONS:
        st.session_state.selected_tab = selected_tab


if "selected_tab" not in st.session_state or st.session_state["selected_tab"] not in TAB_OPTIONS:
    st.session_state.selected_tab = TAB_SOURCE_SETUP


tab1, tab2 = st.tabs(
    TAB_OPTIONS,
    default=st.session_state["selected_tab"],
    key="main_tabs",
    on_change=sync_selected_tab,
)

with tab1:
    st.subheader("Register Source URL")
    st.caption("Enter a base URL. The app will automatically choose RSS/Atom when available and otherwise fall back to HTML listing.")

    with st.form("add_feed_form"):
        name = st.text_input("Name")
        url = st.text_input("Base URL")
        category = st.text_input("Category")
        submitted = st.form_submit_button("Add")

        if submitted:
            if not name.strip() or not url.strip():
                st.error("Please enter both name and base URL.")
            else:
                try:
                    created, detected = add_source_from_base_url(
                        name.strip(),
                        url.strip(),
                        category.strip(),
                    )
                except Exception as error:
                    st.error(f"Failed to inspect URL: {error}")
                else:
                    if created:
                        detected_type_label = "RSS" if detected["source_type"] == "rss" else "HTML listing"
                        st.success(f"Added as {detected_type_label}.")
                        st.caption(f"Base URL: {detected['base_url']}")
                        st.caption(f"Fetch URL: {detected['fetch_url']}")
                        st.caption(detected["detail"])
                        st.rerun()
                    else:
                        st.warning("That source is already registered.")

    st.caption("Google Alerts RSS URLs can still be pasted in bulk below.")
    st.info("Paste one Google Alerts RSS URL per line.")

    with st.form("bulk_google_alert_form"):
        bulk_name_prefix = st.text_input("Bulk name prefix", value="Google Alert")
        bulk_category = st.text_input("Bulk category", key="bulk_category")
        bulk_urls = st.text_area(
            "Google Alerts RSS URLs",
            help="Paste the RSS links from the Google Alerts management page, one per line.",
        )
        bulk_submitted = st.form_submit_button("Add Google Alerts RSS URLs")

        if bulk_submitted:
            urls = parse_google_alert_urls(bulk_urls)
            deduped_urls = unique_urls(urls)
            duplicate_count = len(urls) - len(deduped_urls)

            if not deduped_urls:
                st.error("No RSS URLs were found in the pasted text.")
            else:
                added_count, skipped_count = add_urls_as_feeds(
                    deduped_urls,
                    bulk_name_prefix.strip(),
                    bulk_category.strip(),
                )

                st.info(f"Parsed {len(urls)} URLs, using {len(deduped_urls)} unique URLs.")
                if duplicate_count:
                    st.info(f"Ignored {duplicate_count} duplicate URLs in the pasted list.")
                if added_count:
                    st.success(f"Added {added_count} RSS feeds.")
                if skipped_count:
                    st.info(f"Skipped {skipped_count} URLs because they were already registered.")
                if added_count:
                    st.rerun()

    st.divider()

    if st.button("Fetch Sources Now"):
        count = fetch_active_feeds()
        st.success(f"Fetched {count} new articles.")

    feeds = list_feeds()

    if feeds:
        for feed in feeds:
            feed_id = feed["id"]
            name = feed["name"] or ""
            url = feed["url"] or ""
            base_url = feed["base_url"] or url
            source_type = feed["source_type"] or "rss"
            category = feed["category"] or ""
            is_active = feed["is_active"] or 0

            col1, col2, col3 = st.columns([5, 1, 1])

            with col1:
                st.markdown(f"**{name}**")
                source_label = "RSS" if source_type == "rss" else "HTML"
                caption_parts = []
                if category:
                    caption_parts.append(category)
                caption_parts.append(source_label)
                caption_parts.append(base_url)
                if url != base_url:
                    caption_parts.append(f"Fetch: {url}")
                st.caption(" | ".join(caption_parts))

            with col2:
                active = st.checkbox("Active", value=bool(is_active), key=f"active_{feed_id}")
                if active != bool(is_active):
                    update_feed_status(feed_id, active)
                    st.rerun()

            with col3:
                if st.button("Delete", key=f"delete_{feed_id}"):
                    delete_feed(feed_id)
                    st.rerun()

with tab2:
    st.subheader("Articles")

    col1, col2, col3 = st.columns([3, 1, 1.2])

    with col1:
        keyword = st.text_input("Keyword")

    with col2:
        detail_count = st.number_input("Visible count", min_value=1, max_value=100, value=100)

    with col3:
        read_filter = st.selectbox("Filter", ["Unread", "Read", "All"], index=0)

    if st.button("Fetch RSS", key="fetch_articles_tab"):
        count = fetch_active_feeds()
        st.success(f"Fetched {count} new articles")

    df = list_articles(keyword)

    if df.empty:
        st.info("No articles found.")
    else:
        df["article_key"] = df["article_key"].where(
            df["article_key"].notna() & (df["article_key"] != ""),
            df.apply(lambda row: article_key(row["title"], row["link"]), axis=1),
        )
        df["is_read"] = df["is_read"].fillna(0).astype(bool)
        df = deduplicate_articles(df)

        if read_filter == "Unread":
            filtered_df = df[df["is_read"] == False].copy()
        elif read_filter == "Read":
            filtered_df = df[df["is_read"] == True].copy()
        else:
            filtered_df = df.copy()

        st.divider()
        st.subheader(f"Latest {detail_count} articles")

        visible_df = filtered_df.sort_values(by="published", ascending=False).head(detail_count)

        if visible_df.empty:
            st.info("No articles match the current filter.")
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
                    read_here = st.checkbox("Read", value=is_read, key=f"read_{item_id}")
                    if read_here != is_read:
                        update_article_read_status(current_article_key, read_here)
                        st.rerun()

                with exp_col2:
                    show_detail = st.toggle(
                        f"{published} | {title}",
                        value=False,
                        key=f"show_detail_{item_id}",
                    )

                    if show_detail and not is_read:
                        update_article_read_status(current_article_key, True)
                        is_read = True

                    if show_detail:
                        if row["category"]:
                            st.markdown(f"**Category:** {row['category']}")
                        if row["link"]:
                            st.markdown(f"**Link:** {row['link']}")
                            render_copy_button(text_for_copy(title, link), f"{item_id}")
                        st.markdown("**Summary**")
                        st.write(row["summary"] if row["summary"] else "No summary")
