from datetime import datetime

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, Response

from db import update_article_read_status, update_article_saved_status
from fetcher import fetch_active_feeds
from version import APP_VERSION

from webapp.article_groups import get_article_group_by_id, get_article_groups
from webapp.auto_fetch import maybe_run_auto_fetch
from webapp.context import render_index_template
from webapp.deps import templates

router = APIRouter()


def _list_filter_context(
    keyword: str = "",
    read_filter: str = "all",
    saved_filter: str = "all",
    sort_order: str = "newest",
    limit: int = 50,
):
    return {
        "keyword": keyword,
        "read_filter": read_filter,
        "saved_filter": saved_filter,
        "sort_order": sort_order,
        "limit": limit,
    }


def _article_card_response(request: Request, article_key_value: str, **list_ctx):
    article_groups = get_article_groups(**list_ctx)
    group = next((g for g in article_groups if g["article_key"] == article_key_value), None)
    return templates.TemplateResponse(
        request,
        "partials/article_card.html",
        {
            "request": request,
            "group": group,
            "app_version": APP_VERSION,
            **list_ctx,
        },
    )


@router.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    keyword: str = "",
    read_filter: str = "all",
    saved_filter: str = "all",
    sort_order: str = "newest",
    limit: int = 50,
    fetch_message: str = "",
    fetch_error: str = "",
):
    return render_index_template(
        request,
        keyword=keyword,
        read_filter=read_filter,
        saved_filter=saved_filter,
        sort_order=sort_order,
        limit=limit,
        fetch_message=fetch_message,
        fetch_error=fetch_error,
    )


@router.get("/articles/list", response_class=HTMLResponse)
def article_list(
    request: Request,
    keyword: str = "",
    read_filter: str = "all",
    saved_filter: str = "all",
    sort_order: str = "newest",
    limit: int = 50,
):
    article_groups = get_article_groups(keyword, read_filter, saved_filter, sort_order, limit)
    list_ctx = _list_filter_context(keyword, read_filter, saved_filter, sort_order, limit)
    return templates.TemplateResponse(
        request,
        "partials/article_list.html",
        {
            "request": request,
            "article_groups": article_groups,
            "app_version": APP_VERSION,
            **list_ctx,
        },
    )


@router.get("/articles/detail", response_class=HTMLResponse)
def article_detail(request: Request, article_id: int):
    group = get_article_group_by_id(article_id)
    return templates.TemplateResponse(
        request,
        "partials/article_detail.html",
        {"request": request, "group": group, "app_version": APP_VERSION},
    )


@router.post("/articles/fetch", response_class=HTMLResponse)
def fetch_articles_now(
    request: Request,
    keyword: str = Form(""),
    read_filter: str = Form("all"),
    saved_filter: str = Form("all"),
    sort_order: str = Form("newest"),
    limit: int = Form(50),
):
    fetch_message = ""
    fetch_error = ""

    try:
        inserted_count = fetch_active_feeds()
        fetch_message = f"Fetch completed. {inserted_count} new articles were added."
    except Exception as error:
        fetch_error = f"Fetch failed: {error}"

    return render_index_template(
        request,
        keyword=keyword,
        read_filter=read_filter,
        saved_filter=saved_filter,
        sort_order=sort_order,
        limit=limit,
        fetch_message=fetch_message,
        fetch_error=fetch_error,
    )


@router.post("/articles/auto-fetch")
def auto_fetch_articles():
    maybe_run_auto_fetch(datetime.now())
    return Response(status_code=204)


@router.post("/articles/read", response_class=HTMLResponse)
def update_read(
    request: Request,
    article_key_value: str = Form(...),
    is_read: str = Form(...),
    keyword: str = Form(""),
    read_filter: str = Form("all"),
    saved_filter: str = Form("all"),
    sort_order: str = Form("newest"),
    limit: int = Form(50),
):
    update_article_read_status(article_key_value, is_read == "true")
    list_ctx = _list_filter_context(keyword, read_filter, saved_filter, sort_order, limit)
    return _article_card_response(request, article_key_value, **list_ctx)


@router.post("/articles/save", response_class=HTMLResponse)
def update_saved(
    request: Request,
    article_key_value: str = Form(...),
    is_saved: str = Form(...),
    keyword: str = Form(""),
    read_filter: str = Form("all"),
    saved_filter: str = Form("all"),
    sort_order: str = Form("newest"),
    limit: int = Form(50),
):
    update_article_saved_status(article_key_value, is_saved == "true")
    list_ctx = _list_filter_context(keyword, read_filter, saved_filter, sort_order, limit)
    return _article_card_response(request, article_key_value, **list_ctx)
