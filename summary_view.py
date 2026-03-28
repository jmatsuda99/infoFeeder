from dataclasses import dataclass

import streamlit as st

from db import get_app_state, list_articles, list_feeds
from ui_common import format_jst_datetime, format_jst_time


@dataclass(frozen=True)
class SummaryMetrics:
    total_sources: int
    active_sources: int
    unread_articles: int
    latest_success_at: str
    latest_error_at: str
    error_feed_count: int
    last_fetch_inserted_count: str


def get_summary_metrics_data():
    summary_feeds = list_feeds()
    summary_articles = list_articles("")
    latest_success_at = max((feed["last_success_at"] for feed in summary_feeds if feed["last_success_at"]), default="")
    latest_error_at = max((feed["last_error_at"] for feed in summary_feeds if feed["last_error_at"]), default="")

    return SummaryMetrics(
        total_sources=len(summary_feeds),
        active_sources=sum(1 for feed in summary_feeds if feed["is_active"]),
        unread_articles=0 if summary_articles.empty else int((summary_articles["is_read"].fillna(0) == 0).sum()),
        latest_success_at=latest_success_at,
        latest_error_at=latest_error_at,
        error_feed_count=sum(1 for feed in summary_feeds if feed["last_error_at"]),
        last_fetch_inserted_count=get_app_state("last_fetch_inserted_count", ""),
    )


def render_summary_metrics(next_auto_fetch_at):
    metrics = get_summary_metrics_data()

    metric_col1, metric_col2, metric_col3, metric_col4, metric_col5 = st.columns(5)
    metric_col1.metric("有効ソース", f"{metrics.active_sources}", delta=f"全 {metrics.total_sources} 件")
    metric_col2.metric("未読記事", f"{metrics.unread_articles}")
    metric_col3.metric(
        "最終成功",
        format_jst_datetime(metrics.latest_success_at) if metrics.latest_success_at else "未成功",
    )
    metric_col4.metric(
        "最終取得件数",
        metrics.last_fetch_inserted_count if metrics.last_fetch_inserted_count != "" else "-",
    )
    metric_col5.metric("次回取得", format_jst_time(next_auto_fetch_at))

    if metrics.latest_success_at:
        st.caption(f"最終取得成功: {format_jst_datetime(metrics.latest_success_at)}")

    if metrics.latest_error_at and metrics.latest_error_at >= metrics.latest_success_at:
        st.warning(
            f"{metrics.error_feed_count} 件のソースで取得失敗があります。"
            f"最新失敗: {format_jst_datetime(metrics.latest_error_at)}"
        )
