import json
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

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
    add_excluded_domain,
    delete_feed,
    delete_excluded_domain,
    get_app_state,
    init_db,
    list_articles,
    list_excluded_domains,
    list_feeds,
    update_article_read_status,
    update_article_saved_status,
    update_articles_read_status,
    update_feed_status,
)
from exclusion_rules import resolve_excluded_domain_keywords
from fetcher import discover_feed_source, fetch_active_feeds
from version import APP_VERSION


st.set_page_config(page_title="Google Alerts RSS Viewer", layout="wide")
st.title("Google Alerts RSS Viewer")

init_db()

TAB_SOURCE_SETUP = "ソース設定"
TAB_ARTICLES = "記事一覧"
TAB_OPTIONS = [TAB_SOURCE_SETUP, TAB_ARTICLES]
READ_FILTER_OPTIONS = ["未読", "既読", "すべて"]
SORT_ORDER_OPTIONS = ["新しい順", "古い順", "保存記事を先頭"]
JST = ZoneInfo("Asia/Tokyo")


def fetch_articles_with_feedback(success_message):
    count = fetch_active_feeds()
    st.success(success_message.format(count=count))
    return count


def render_app_shell(next_fetch_at):
    st.markdown(
        """
        <style>
        .stApp {
            background: linear-gradient(180deg, #f4f7fb 0%, #eef2f7 100%);
        }
        .block-container {
            max-width: 1180px;
            padding-top: 1.8rem;
            padding-bottom: 2.5rem;
        }
        h1, h2, h3 {
            color: #132238;
            letter-spacing: -0.01em;
        }
        [data-baseweb="tab-list"] {
            gap: 0.4rem;
            background: #e8edf4;
            padding: 0.3rem;
            border-radius: 0.9rem;
        }
        button[data-baseweb="tab"] {
            background: transparent;
            border-radius: 0.7rem;
            color: #425466;
            font-weight: 600;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            background: #ffffff;
            color: #132238;
            box-shadow: 0 1px 2px rgba(16, 24, 40, 0.08);
        }
        div[data-testid="stForm"],
        div[data-testid="stVerticalBlock"] div[data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 16px;
        }
        div[data-testid="stForm"] {
            background: rgba(255, 255, 255, 0.82);
            border: 1px solid #d9e2ec;
            padding: 1rem 1rem 0.4rem 1rem;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
        }
        div[data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.82);
            border: 1px solid #d9e2ec;
            padding: 0.9rem 1rem;
            border-radius: 14px;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
        }
        div[data-testid="stMetric"] label {
            color: #5b6b7d;
            font-weight: 600;
        }
        div[data-testid="stMetricValue"] {
            color: #132238;
        }
        .if-muted {
            color: #5b6b7d;
            font-size: 0.95rem;
        }
        .if-card-title {
            color: #132238;
            font-weight: 700;
            font-size: 1rem;
            margin-bottom: 0.2rem;
        }
        .if-badge {
            display: inline-block;
            padding: 0.18rem 0.55rem;
            border-radius: 999px;
            background: #e7eef7;
            color: #28435c;
            font-size: 0.76rem;
            font-weight: 700;
            margin-right: 0.35rem;
            margin-bottom: 0.35rem;
        }
        .if-badge-muted {
            background: #eef2f6;
            color: #526273;
        }
        .if-meta-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.9rem;
            margin-top: 0.45rem;
        }
        .if-meta-item {
            color: #526273;
            font-size: 0.85rem;
            font-weight: 600;
        }
        .if-page-intro {
            background: rgba(255, 255, 255, 0.82);
            border: 1px solid #d9e2ec;
            border-radius: 18px;
            padding: 1rem 1.15rem;
            margin-bottom: 1rem;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
        }
        .if-control-panel {
            background: rgba(255, 255, 255, 0.82);
            border: 1px solid #d9e2ec;
            border-radius: 16px;
            padding: 1rem 1rem 0.25rem 1rem;
            margin-bottom: 1rem;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.05);
        }
        div[data-testid="stCheckbox"] label,
        div[data-testid="stToggle"] label {
            font-weight: 600;
        }
        .stButton > button {
            border-radius: 10px;
            border: 1px solid #c7d3e0;
            background: #f8fafc;
            color: #18324b;
            font-weight: 600;
        }
        .stButton > button[kind="primary"] {
            background: #23415f;
            color: #ffffff;
            border-color: #23415f;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        f"""
        <div class="if-page-intro">
            <div class="if-card-title">Google Alerts RSS Viewer</div>
            <div class="if-muted">Ver.{APP_VERSION}</div>
            <div class="if-muted">ソースを管理し、未読記事を確認し、30分ごとに自動更新します。次回取得予定: {format_jst_datetime(next_fetch_at, include_date=True)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def format_jst_datetime(value, include_date=False):
    dt = None

    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value.strip():
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            try:
                dt = parsedate_to_datetime(value)
            except (TypeError, ValueError):
                return value

    if dt is None:
        return ""

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    else:
        dt = dt.astimezone(JST)

    if include_date:
        return dt.strftime("%Y-%m-%d %H:%M JST")
    return dt.strftime("%Y-%m-%d %H:%M:%S JST")


def format_jst_time(value):
    dt = None

    if isinstance(value, datetime):
        dt = value
    else:
        formatted = format_jst_datetime(value)
        if not formatted:
            return ""
        return formatted.split(" ")[1]

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=JST)
    else:
        dt = dt.astimezone(JST)
    return dt.strftime("%H:%M")


def get_next_half_hour(now):
    next_half_hour = now.replace(second=0, microsecond=0)
    if now.minute < 30:
        next_half_hour = next_half_hour.replace(minute=30)
    else:
        next_half_hour = (next_half_hour + timedelta(hours=1)).replace(minute=0)
    return next_half_hour


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
        st.query_params["tab"] = selected_tab


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


def initialize_article_filters():
    if "article_keyword" not in st.session_state:
        st.session_state.article_keyword = get_query_param("keyword", "")

    if "article_detail_count" not in st.session_state:
        st.session_state.article_detail_count = get_int_query_param("count", 100, min_value=1, max_value=100)

    if "article_read_filter" not in st.session_state:
        initial_read_filter = get_query_param("read", READ_FILTER_OPTIONS[0])
        st.session_state.article_read_filter = (
            initial_read_filter if initial_read_filter in READ_FILTER_OPTIONS else READ_FILTER_OPTIONS[0]
        )

    if "article_sort_order" not in st.session_state:
        initial_sort_order = get_query_param("sort", SORT_ORDER_OPTIONS[0])
        st.session_state.article_sort_order = (
            initial_sort_order if initial_sort_order in SORT_ORDER_OPTIONS else SORT_ORDER_OPTIONS[0]
        )


def get_summary_metrics_data():
    summary_feeds = list_feeds()
    summary_articles = list_articles("")
    latest_success_at = max((feed["last_success_at"] for feed in summary_feeds if feed["last_success_at"]), default="")
    latest_error_at = max((feed["last_error_at"] for feed in summary_feeds if feed["last_error_at"]), default="")

    return {
        "total_sources": len(summary_feeds),
        "active_sources": sum(1 for feed in summary_feeds if feed["is_active"]),
        "unread_articles": 0 if summary_articles.empty else int((summary_articles["is_read"].fillna(0) == 0).sum()),
        "latest_success_at": latest_success_at,
        "latest_error_at": latest_error_at,
        "error_feed_count": sum(1 for feed in summary_feeds if feed["last_error_at"]),
        "last_fetch_inserted_count": get_app_state("last_fetch_inserted_count", ""),
    }


def render_summary_metrics(next_auto_fetch_at):
    metrics = get_summary_metrics_data()

    metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = st.columns(5)
    metric_col1.metric("有効ソース", f"{metrics['active_sources']}", delta=f"全 {metrics['total_sources']} 件")
    metric_col2.metric("未読記事", f"{metrics['unread_articles']}")
    metric_col3.metric(
        "最終成功",
        format_jst_datetime(metrics["latest_success_at"]) if metrics["latest_success_at"] else "未成功",
    )
    metric_col4.metric(
        "最終取得件数",
        metrics["last_fetch_inserted_count"] if metrics["last_fetch_inserted_count"] != "" else "-",
    )
    metric_col5.metric("次回取得", format_jst_time(next_auto_fetch_at))

    if metrics["latest_success_at"]:
        st.caption(f"最終取得成功: {format_jst_datetime(metrics['latest_success_at'])}")

    if metrics["latest_error_at"] and metrics["latest_error_at"] >= metrics["latest_success_at"]:
        st.warning(
            f"{metrics['error_feed_count']} 件のソースで取得失敗があります。"
            f"最新失敗: {format_jst_datetime(metrics['latest_error_at'])}"
        )


def build_feed_badges(source_type, category):
    source_label = "RSS" if source_type == "rss" else "HTML"
    badge_html = f'<span class="if-badge">{source_label}</span>'
    if category:
        badge_html += f'<span class="if-badge if-badge-muted">{category}</span>'
    return badge_html


def render_feed_card(feed):
    feed_id = feed["id"]
    name = feed["name"] or ""
    url = feed["url"] or ""
    base_url = feed["base_url"] or url
    source_type = feed["source_type"] or "rss"
    category = feed["category"] or ""
    is_active = feed["is_active"] or 0
    item_count = int(feed["item_count"] or 0)
    last_fetched_at = format_jst_datetime(feed["last_fetched_at"]) if feed["last_fetched_at"] else "未取得"
    last_success_at = format_jst_datetime(feed["last_success_at"]) if feed["last_success_at"] else "未成功"
    last_error_at = format_jst_datetime(feed["last_error_at"]) if feed["last_error_at"] else ""
    last_error_message = feed["last_error_message"] or ""

    with st.container(border=True):
        col1, col2, col3 = st.columns([5, 1, 1])

        with col1:
            badge_html = build_feed_badges(source_type, category)
            st.markdown(f'<div class="if-card-title">{name}</div>{badge_html}', unsafe_allow_html=True)
            st.markdown(f'<div class="if-muted">{base_url}</div>', unsafe_allow_html=True)
            if url != base_url:
                st.caption(f"取得URL: {url}")
            st.markdown(
                f"""
                <div class="if-meta-row">
                    <div class="if-meta-item">記事数: {item_count}</div>
                    <div class="if-meta-item">最終取得: {last_fetched_at}</div>
                    <div class="if-meta-item">最終成功: {last_success_at}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if last_error_at:
                st.warning(f"最終失敗: {last_error_at} | {last_error_message}")

        with col2:
            active = st.checkbox("有効", value=bool(is_active), key=f"active_{feed_id}")
            if active != bool(is_active):
                update_feed_status(feed_id, active)
                st.rerun()

        with col3:
            if st.button("削除", key=f"delete_{feed_id}"):
                delete_feed(feed_id)
                st.rerun()


def render_excluded_domain_section():
    st.divider()
    st.subheader("除外ドメイン設定")
    st.caption("媒体名やドメイン名を追加すると、そのドメインの記事を取得対象と一覧表示から除外します。")

    with st.form("add_excluded_domain_form"):
        excluded_name = st.text_input(
            "除外対象名",
            help="例: 西日本新聞 / pando / nikkei。既知の媒体名は対応ドメインに自動変換します。",
        )
        excluded_submitted = st.form_submit_button("除外対象を追加")

        if excluded_submitted:
            if not excluded_name.strip():
                st.error("除外対象名を入力してください。")
            else:
                created = add_excluded_domain(excluded_name.strip())
                if created:
                    resolved_keywords = ", ".join(resolve_excluded_domain_keywords((excluded_name.strip(),)))
                    st.success("除外対象を追加しました。")
                    st.caption(f"適用ドメインキーワード: {resolved_keywords}")
                    st.rerun()
                else:
                    st.warning("その除外対象はすでに登録されています。")

    excluded_domains = list_excluded_domains()
    if excluded_domains:
        st.markdown('<div class="if-muted" style="margin-bottom:0.6rem;">登録済み除外対象</div>', unsafe_allow_html=True)
        for excluded_domain in excluded_domains:
            excluded_id = excluded_domain["id"]
            excluded_name = excluded_domain["name"] or ""
            resolved_keywords = ", ".join(resolve_excluded_domain_keywords((excluded_name,)))

            with st.container(border=True):
                col1, col2 = st.columns([6, 1])
                with col1:
                    st.markdown(f'<div class="if-card-title">{excluded_name}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="if-muted">適用ドメインキーワード: {resolved_keywords}</div>', unsafe_allow_html=True)
                with col2:
                    if st.button("削除", key=f"delete_excluded_domain_{excluded_id}"):
                        delete_excluded_domain(excluded_id)
                        st.rerun()


def render_bulk_google_alert_messages(urls, deduped_urls, duplicate_count, added_count, skipped_count):
    st.info(f"{len(urls)} 件を解析し、そのうち {len(deduped_urls)} 件のユニーク URL を使用します。")
    if duplicate_count:
        st.info(f"重複していた {duplicate_count} 件は無視しました。")
    if added_count:
        st.success(f"{added_count} 件の RSS を追加しました。")
    if skipped_count:
        st.info(f"{skipped_count} 件は登録済みのため追加しませんでした。")


def render_source_setup_tab():
    st.subheader("ソースURL登録")
    st.caption("ベースURLを入力すると、RSS/Atom を優先して自動判定し、見つからない場合は HTML listing として登録します。")

    with st.form("add_feed_form"):
        name = st.text_input("名前")
        url = st.text_input("ベースURL")
        category = st.text_input("カテゴリ")
        submitted = st.form_submit_button("追加")

        if submitted:
            if not name.strip() or not url.strip():
                st.error("名前とベースURLを入力してください。")
            else:
                try:
                    created, detected = add_source_from_base_url(
                        name.strip(),
                        url.strip(),
                        category.strip(),
                    )
                except Exception as error:
                    st.error(f"URL の確認に失敗しました: {error}")
                else:
                    if created:
                        detected_type_label = "RSS" if detected["source_type"] == "rss" else "HTML listing"
                        st.success(f"{detected_type_label} として追加しました。")
                        st.caption(f"ベースURL: {detected['base_url']}")
                        st.caption(f"取得URL: {detected['fetch_url']}")
                        st.caption(detected["detail"])
                        st.rerun()
                    else:
                        st.warning("そのソースはすでに登録されています。")

    st.caption("Google Alerts の RSS URL は下の一括登録からそのまま追加できます。")
    st.info("Google Alerts の RSS URL を 1 行に 1 件ずつ貼り付けてください。")

    with st.form("bulk_google_alert_form"):
        bulk_name_prefix = st.text_input("一括登録名プレフィックス", value="Google Alert")
        bulk_category = st.text_input("一括登録カテゴリ", key="bulk_category")
        bulk_urls = st.text_area(
            "Google Alerts RSS URL 一覧",
            help="Google Alerts 管理画面の RSS リンクを 1 行に 1 件ずつ貼り付けてください。",
        )
        bulk_submitted = st.form_submit_button("Google Alerts RSS を追加")

        if bulk_submitted:
            urls = parse_google_alert_urls(bulk_urls)
            deduped_urls = unique_urls(urls)
            duplicate_count = len(urls) - len(deduped_urls)

            if not deduped_urls:
                st.error("貼り付けた内容から RSS URL を見つけられませんでした。")
            else:
                added_count, skipped_count = add_urls_as_feeds(
                    deduped_urls,
                    bulk_name_prefix.strip(),
                    bulk_category.strip(),
                )

                render_bulk_google_alert_messages(urls, deduped_urls, duplicate_count, added_count, skipped_count)
                if added_count:
                    st.rerun()

    st.divider()

    if st.button("いま取得する"):
        fetch_articles_with_feedback("{count} 件の新着記事を取得しました。")

    feeds = list_feeds()
    if feeds:
        st.markdown('<div class="if-muted" style="margin-bottom:0.6rem;">登録済みソース</div>', unsafe_allow_html=True)
        for feed in feeds:
            render_feed_card(feed)

    render_excluded_domain_section()


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


def render_mark_visible_read_action(unread_visible_keys):
    action_col1, action_col2 = st.columns([2, 6])
    with action_col1:
        if st.button("表示中をすべて既読", key="mark_visible_read"):
            update_articles_read_status(unread_visible_keys, True)
            st.rerun()


def render_articles_tab():
    st.subheader("記事一覧")

    with st.container(border=True):
        st.markdown('<div class="if-muted" style="margin-bottom:0.6rem;">表示条件</div>', unsafe_allow_html=True)
        col1, col2, col3, col4 = st.columns([3.2, 1.2, 1.4, 1.3])

        with col1:
            keyword = st.text_input("キーワード", key="article_keyword")

        with col2:
            detail_count = st.number_input("表示件数", min_value=1, max_value=100, key="article_detail_count")

        with col3:
            read_filter = st.selectbox("表示", READ_FILTER_OPTIONS, key="article_read_filter")

        with col4:
            sort_order = st.selectbox("並び順", SORT_ORDER_OPTIONS, key="article_sort_order")
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
    if unread_visible_keys:
        render_mark_visible_read_action(unread_visible_keys)

    for _, row in visible_df.iterrows():
        render_article_card(row)


def initialize_selected_tab():
    query_tab = st.query_params.get("tab", TAB_SOURCE_SETUP)
    if query_tab not in TAB_OPTIONS:
        query_tab = TAB_SOURCE_SETUP

    if "selected_tab" not in st.session_state or st.session_state["selected_tab"] not in TAB_OPTIONS:
        st.session_state.selected_tab = query_tab
    elif st.session_state["selected_tab"] != query_tab:
        st.session_state.selected_tab = query_tab

    st.query_params["tab"] = st.session_state["selected_tab"]


def render_main_tabs():
    tab1, tab2 = st.tabs(
        TAB_OPTIONS,
        default=st.session_state["selected_tab"],
        key="main_tabs",
        on_change=sync_selected_tab,
    )

    with tab1:
        render_source_setup_tab()

    with tab2:
        render_articles_tab()


next_auto_fetch_at = get_next_half_hour(datetime.now())
render_app_shell(next_auto_fetch_at)
initialize_selected_tab()
initialize_article_filters()
render_summary_metrics(next_auto_fetch_at)
render_main_tabs()
