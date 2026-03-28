import streamlit as st

from db import (
    add_excluded_domain,
    add_feed,
    delete_excluded_domain,
    delete_feed,
    list_excluded_domains,
    list_feeds,
    update_feed_status,
)
from exclusion_rules import resolve_excluded_domain_keywords
from fetcher import discover_feed_source
from ui_common import fetch_articles_with_feedback, format_jst_datetime


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


def build_feed_badges(source_type, category):
    source_label = "RSS" if source_type == "rss" else "HTML"
    badge_html = f'<span class="if-badge">{source_label}</span>'
    if category:
        badge_html += f'<span class="if-badge if-badge-muted">{category}</span>'
    return badge_html


def handle_add_feed_submission(name, url, category):
    if not name.strip() or not url.strip():
        st.error("名前とベースURLを入力してください。")
        return

    try:
        created, detected = add_source_from_base_url(
            name.strip(),
            url.strip(),
            category.strip(),
        )
    except Exception as error:
        st.error(f"URL の確認に失敗しました: {error}")
        return

    if created:
        detected_type_label = "RSS" if detected["source_type"] == "rss" else "HTML listing"
        st.success(f"{detected_type_label} として追加しました。")
        st.caption(f"ベースURL: {detected['base_url']}")
        st.caption(f"取得URL: {detected['fetch_url']}")
        st.caption(detected["detail"])
        st.rerun()

    st.warning("そのソースはすでに登録されています。")


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


def handle_bulk_google_alert_submission(bulk_urls, bulk_name_prefix, bulk_category, parse_google_alert_urls, unique_urls):
    urls = parse_google_alert_urls(bulk_urls)
    deduped_urls = unique_urls(urls)
    duplicate_count = len(urls) - len(deduped_urls)

    if not deduped_urls:
        st.error("貼り付けた内容から RSS URL を見つけられませんでした。")
        return

    added_count, skipped_count = add_urls_as_feeds(
        deduped_urls,
        bulk_name_prefix.strip(),
        bulk_category.strip(),
    )

    render_bulk_google_alert_messages(urls, deduped_urls, duplicate_count, added_count, skipped_count)
    if added_count:
        st.rerun()


def render_source_setup_tab(parse_google_alert_urls, unique_urls):
    st.subheader("ソースURL登録")
    st.caption("ベースURLを入力すると、RSS/Atom を優先して自動判定し、見つからない場合は HTML listing として登録します。")

    with st.form("add_feed_form"):
        name = st.text_input("名前")
        url = st.text_input("ベースURL")
        category = st.text_input("カテゴリ")
        submitted = st.form_submit_button("追加")

        if submitted:
            handle_add_feed_submission(name, url, category)

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
            handle_bulk_google_alert_submission(
                bulk_urls,
                bulk_name_prefix,
                bulk_category,
                parse_google_alert_urls,
                unique_urls,
            )

    st.divider()

    if st.button("いま取得する"):
        fetch_articles_with_feedback("{count} 件の新着記事を取得しました。")

    feeds = list_feeds()
    if feeds:
        st.markdown('<div class="if-muted" style="margin-bottom:0.6rem;">登録済みソース</div>', unsafe_allow_html=True)
        for feed in feeds:
            render_feed_card(feed)

    render_excluded_domain_section()
