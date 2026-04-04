from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from article_utils import article_key
from db import (
    add_feed,
    delete_feed,
    get_app_state,
    get_summary_metrics_row,
    list_articles,
    list_feeds,
    set_app_state,
    update_feed_status,
    update_article_read_status,
    update_article_saved_status,
)
from fetcher import discover_feed_source, fetch_active_feeds
from ui_common import format_jst_datetime
from version import APP_VERSION


BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="infoFeeder Web", debug=True)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
AUTO_FETCH_SLOT_KEY = "last_auto_fetch_slot"


def get_next_half_hour(now):
    next_half_hour = now.replace(second=0, microsecond=0)
    if now.minute < 30:
        return next_half_hour.replace(minute=30)
    return (next_half_hour + timedelta(hours=1)).replace(minute=0)


def get_next_auto_fetch_delay_ms(now):
    next_fetch_at = get_next_half_hour(now)
    return max(1000, int((next_fetch_at - now).total_seconds() * 1000) + 1000)


def maybe_run_auto_fetch(now):
    if now.minute not in (0, 30):
        return 0

    current_slot = now.strftime("%Y-%m-%dT%H:%M")
    if get_app_state(AUTO_FETCH_SLOT_KEY, "") == current_slot:
        return 0

    inserted_count = fetch_active_feeds()
    set_app_state(AUTO_FETCH_SLOT_KEY, current_slot)
    return inserted_count


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
    return {
        "request": request,
        "app_version": APP_VERSION,
        "metrics": get_summary_metrics_row(),
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
    groups = []
    if df.empty:
        return groups

    for current_article_key, group_df in df.groupby("article_key", sort=False):
        sorted_group = group_df.sort_values(by=["published", "id"], ascending=[False, False]).copy()
        representative = sorted_group.iloc[0]
        groups.append(
            {
                "id": int(representative["id"]),
                "article_key": current_article_key,
                "title": representative["title"] or "(no title)",
                "link": representative["link"] or "",
                "source_name": representative["source_name"] or "",
                "category": representative["category"] or "",
                "published": representative["published"] or "",
                "published_display": format_jst_datetime(representative["published"]) if representative["published"] else "",
                "summary": representative["summary"] or "",
                "is_read": bool(sorted_group["is_read"].any()),
                "is_saved": bool(sorted_group["is_saved"].any()),
                "group_count": int(len(sorted_group)),
                "related_articles": [
                    {
                        "id": int(row["id"]),
                        "title": row["title"] or "(no title)",
                        "link": row["link"] or "",
                        "source_name": row["source_name"] or "",
                        "published_display": format_jst_datetime(row["published"]) if row["published"] else "",
                    }
                    for _, row in sorted_group.head(5).iterrows()
                ],
            }
        )

    return groups


def get_article_groups(keyword="", read_filter="all", saved_filter="all", sort_order="newest", limit=50):
    df = prepare_article_dataframe(keyword)
    groups = build_article_groups(df)

    if read_filter == "unread":
        groups = [group for group in groups if not group["is_read"]]
    elif read_filter == "read":
        groups = [group for group in groups if group["is_read"]]

    if saved_filter == "saved":
        groups = [group for group in groups if group["is_saved"]]

    reverse = sort_order != "oldest"
    groups.sort(key=lambda group: (group["published"], group["id"]), reverse=reverse)
    if sort_order == "saved":
        groups.sort(key=lambda group: group["is_saved"], reverse=True)
    return groups[:limit]


def get_article_group_by_id(article_id):
    groups = get_article_groups(limit=100000)
    return next((group for group in groups if group["id"] == article_id), None)


def get_feed_rows():
    feeds = []
    for feed in list_feeds():
        feeds.append(
            {
                "id": int(feed["id"]),
                "name": feed["name"] or "",
                "url": feed["url"] or "",
                "base_url": feed["base_url"] or feed["url"] or "",
                "source_type": feed["source_type"] or "rss",
                "category": feed["category"] or "",
                "is_active": bool(feed["is_active"]),
                "item_count": int(feed["item_count"] or 0),
                "last_fetched_at": format_jst_datetime(feed["last_fetched_at"]) if feed["last_fetched_at"] else "",
                "last_success_at": format_jst_datetime(feed["last_success_at"]) if feed["last_success_at"] else "",
                "last_error_at": format_jst_datetime(feed["last_error_at"]) if feed["last_error_at"] else "",
                "last_error_message": feed["last_error_message"] or "",
            }
        )
    return feeds


@app.get("/", response_class=HTMLResponse)
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


@app.get("/articles/list", response_class=HTMLResponse)
def article_list(
    request: Request,
    keyword: str = "",
    read_filter: str = "all",
    saved_filter: str = "all",
    sort_order: str = "newest",
    limit: int = 50,
):
    article_groups = get_article_groups(keyword, read_filter, saved_filter, sort_order, limit)
    return templates.TemplateResponse(
        request,
        "partials/article_list.html",
        {
            "request": request,
            "article_groups": article_groups,
            "app_version": APP_VERSION,
            "keyword": keyword,
            "read_filter": read_filter,
            "saved_filter": saved_filter,
            "sort_order": sort_order,
            "limit": limit,
        },
    )


@app.get("/articles/detail", response_class=HTMLResponse)
def article_detail(request: Request, article_id: int):
    group = get_article_group_by_id(article_id)
    return templates.TemplateResponse(
        request,
        "partials/article_detail.html",
        {"request": request, "group": group, "app_version": APP_VERSION},
    )


@app.post("/articles/fetch", response_class=HTMLResponse)
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


@app.post("/articles/auto-fetch")
def auto_fetch_articles():
    maybe_run_auto_fetch(datetime.now())
    return Response(status_code=204)


@app.post("/articles/read", response_class=HTMLResponse)
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
    article_groups = get_article_groups(keyword, read_filter, saved_filter, sort_order, limit)
    group = next((group for group in article_groups if group["article_key"] == article_key_value), None)
    return templates.TemplateResponse(
        request,
        "partials/article_card.html",
        {
            "request": request,
            "group": group,
            "app_version": APP_VERSION,
            "keyword": keyword,
            "read_filter": read_filter,
            "saved_filter": saved_filter,
            "sort_order": sort_order,
            "limit": limit,
        },
    )


@app.post("/articles/save", response_class=HTMLResponse)
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
    article_groups = get_article_groups(keyword, read_filter, saved_filter, sort_order, limit)
    group = next((group for group in article_groups if group["article_key"] == article_key_value), None)
    return templates.TemplateResponse(
        request,
        "partials/article_card.html",
        {
            "request": request,
            "group": group,
            "app_version": APP_VERSION,
            "keyword": keyword,
            "read_filter": read_filter,
            "saved_filter": saved_filter,
            "sort_order": sort_order,
            "limit": limit,
        },
    )


@app.get("/sources", response_class=HTMLResponse)
def sources(request: Request):
    return render_sources_template(request)


@app.post("/sources/add", response_class=HTMLResponse)
def add_source(
    request: Request,
    name: str = Form(""),
    url: str = Form(""),
    category: str = Form(""),
):
    error_message = ""
    success_message = ""

    if not name.strip() or not url.strip():
        error_message = "Name and URL are required."
    else:
        try:
            detected = discover_feed_source(url.strip())
            created = add_feed(
                name.strip(),
                detected["fetch_url"],
                category.strip(),
                source_type=detected["source_type"],
                base_url=detected["base_url"],
            )
            if created:
                success_message = f"Added source as {detected['source_type']}."
            else:
                error_message = "That source already exists."
        except Exception as error:
            error_message = f"Failed to add source: {error}"

    return render_sources_template(
        request,
        error_message=error_message,
        success_message=success_message,
    )


@app.post("/sources/toggle", response_class=HTMLResponse)
def toggle_source(request: Request, feed_id: int = Form(...), is_active: str = Form(...)):
    update_feed_status(feed_id, is_active == "true")
    return templates.TemplateResponse(
        request,
        "partials/feed_list.html",
        {"request": request, "feeds": get_feed_rows(), "app_version": APP_VERSION},
    )


@app.post("/sources/delete", response_class=HTMLResponse)
def remove_source(request: Request, feed_id: int = Form(...)):
    delete_feed(feed_id)
    return templates.TemplateResponse(
        request,
        "partials/feed_list.html",
        {"request": request, "feeds": get_feed_rows(), "app_version": APP_VERSION},
    )


@app.get("/health")
def health():
    return {"ok": True}
