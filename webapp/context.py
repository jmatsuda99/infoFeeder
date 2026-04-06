from datetime import datetime

from fastapi import Request

from db import get_summary_metrics_row
from ui_common import format_jst_datetime
from version import APP_VERSION

from webapp.article_groups import get_article_groups
from webapp.auto_fetch import get_next_auto_fetch_delay_ms
from webapp.deps import templates
from webapp.feeds_display import get_feed_rows


def build_index_context(
    request: Request,
    *,
    keyword: str = "",
    read_filter: str = "all",
    saved_filter: str = "all",
    sort_order: str = "newest",
    limit: int = 50,
    fetch_message: str = "",
    fetch_error: str = "",
):
    now = datetime.now()
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
    return {
        "request": request,
        "app_version": APP_VERSION,
        "metrics": metrics,
        "article_groups": get_article_groups(keyword, read_filter, saved_filter, sort_order, limit),
        "keyword": keyword,
        "read_filter": read_filter,
        "saved_filter": saved_filter,
        "sort_order": sort_order,
        "limit": limit,
        "fetch_message": fetch_message,
        "fetch_error": fetch_error,
        "next_auto_fetch_delay_ms": get_next_auto_fetch_delay_ms(now),
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
        "app_version": APP_VERSION,
        "feeds": get_feed_rows(),
        "error_message": error_message,
        "success_message": success_message,
        "next_auto_fetch_delay_ms": get_next_auto_fetch_delay_ms(datetime.now()),
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
