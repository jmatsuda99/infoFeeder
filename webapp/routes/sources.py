from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from db import add_feed, delete_feed, update_feed_status
from fetcher import discover_feed_source
from version import APP_VERSION

from webapp.context import render_sources_template
from webapp.deps import templates
from webapp.feeds_display import get_feed_rows

router = APIRouter()


@router.get("/sources", response_class=HTMLResponse)
def sources(request: Request):
    return render_sources_template(request)


@router.post("/sources/add", response_class=HTMLResponse)
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


@router.post("/sources/toggle", response_class=HTMLResponse)
def toggle_source(request: Request, feed_id: int = Form(...), is_active: str = Form(...)):
    update_feed_status(feed_id, is_active == "true")
    return templates.TemplateResponse(
        request,
        "partials/feed_list.html",
        {"request": request, "feeds": get_feed_rows(), "app_version": APP_VERSION},
    )


@router.post("/sources/delete", response_class=HTMLResponse)
def remove_source(request: Request, feed_id: int = Form(...)):
    delete_feed(feed_id)
    return templates.TemplateResponse(
        request,
        "partials/feed_list.html",
        {"request": request, "feeds": get_feed_rows(), "app_version": APP_VERSION},
    )
