from fastapi import Request

import category_classifier
from db import get_summary_metrics_row
from jst_format import format_jst_datetime
from version import read_app_version

from webapp.article_groups import get_article_groups
from webapp.deps import templates
from webapp.feeds_display import get_feed_rows


def get_formatted_metrics():
    metrics = get_summary_metrics_row()
    metrics["latest_success_at"] = (
        format_jst_datetime(metrics["latest_success_at"], include_date=True)
        if metrics["latest_success_at"]
        else ""
    )
    metrics["latest_error_at"] = (
        format_jst_datetime(metrics["latest_error_at"], include_date=True)
        if metrics["latest_error_at"]
        else ""
    )
    return metrics


def build_index_context(
    request: Request,
    *,
    keyword: str = "",
    read_filter: str = "all",
    saved_filter: str = "all",
    category_filter: str = "",
    rescue_filter: str = "all",
    sort_order: str = "newest",
    limit: int = 50,
    fetch_message: str = "",
    fetch_error: str = "",
):
    return {
        "request": request,
        "app_version": read_app_version(),
        "metrics": get_formatted_metrics(),
        "article_groups": get_article_groups(keyword, category_filter, rescue_filter, read_filter, saved_filter, sort_order, limit),
        "keyword": keyword,
        "read_filter": read_filter,
        "saved_filter": saved_filter,
        "category_filter": category_filter,
        "category_options": category_classifier.CATEGORY_TAXONOMY,
        "rescue_filter": rescue_filter,
        "rescue_options": [
            ("all", "すべて表示"),
            ("hide_rescue", "低優先度を除外"),
            ("rescue_only", "低優先度のみ表示"),
        ],
        "sort_order": sort_order,
        "limit": limit,
        "fetch_message": fetch_message,
        "fetch_error": fetch_error,
    }


def render_index_template(request: Request, **context):
    return templates.TemplateResponse(
        request,
        "index.html",
        build_index_context(request, **context),
    )


def build_sources_context(request: Request, *, error_message: str = "", success_message: str = ""):
    return {
        "request": request,
        "app_version": read_app_version(),
        "feeds": get_feed_rows(),
        "category_options": category_classifier.CATEGORY_TAXONOMY,
        "error_message": error_message,
        "success_message": success_message,
    }


def render_sources_template(request: Request, *, error_message: str = "", success_message: str = ""):
    return templates.TemplateResponse(
        request,
        "sources.html",
        build_sources_context(
            request,
            error_message=error_message,
            success_message=success_message,
        ),
    )
