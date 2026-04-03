from dataclasses import dataclass

import streamlit as st

from db import get_app_state, get_summary_metrics_row
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
    metrics_row = get_summary_metrics_row()

    return SummaryMetrics(
        total_sources=metrics_row["total_sources"],
        active_sources=metrics_row["active_sources"],
        unread_articles=metrics_row["unread_articles"],
        latest_success_at=metrics_row["latest_success_at"],
        latest_error_at=metrics_row["latest_error_at"],
        error_feed_count=metrics_row["error_feed_count"],
        last_fetch_inserted_count=get_app_state("last_fetch_inserted_count", ""),
    )


def render_summary_metrics(next_auto_fetch_at):
    metrics = get_summary_metrics_data()

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("有効ソース", f"{metrics.active_sources}", delta=f"全 {metrics.total_sources} 件")
    metric_col2.metric("未読記事", f"{metrics.unread_articles}")
    metric_col3.metric(
        "最終取得件数",
        metrics.last_fetch_inserted_count if metrics.last_fetch_inserted_count != "" else "-",
    )
    metric_col4.metric("次回取得", format_jst_time(next_auto_fetch_at))

    if metrics.latest_success_at:
        st.caption(f"最終取得成功: {format_jst_datetime(metrics.latest_success_at)}")

    if metrics.latest_error_at and metrics.latest_error_at >= metrics.latest_success_at:
        st.warning(
            f"{metrics.error_feed_count} 件のソースで取得失敗があります。"
            f" 最新失敗: {format_jst_datetime(metrics.latest_error_at)}"
        )
