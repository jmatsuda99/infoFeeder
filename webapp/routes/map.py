from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from version import read_app_version
from webapp.article_map import get_saved_article_map, get_saved_article_map_revision
from webapp.deps import templates


router = APIRouter()


@router.get("/map", response_class=HTMLResponse)
def article_map(request: Request):
    return templates.TemplateResponse(
        request,
        "map.html",
        {
            "request": request,
            "app_version": read_app_version(),
            "article_map": get_saved_article_map(),
        },
    )


@router.get("/map/revision")
def article_map_revision():
    return {"revision": get_saved_article_map_revision()}
