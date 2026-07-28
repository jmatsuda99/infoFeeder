import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from db import init_db
from fetcher import fetch_active_feeds
from webapp.deps import BASE_DIR
from webapp.routes import articles, map, sources


logger = logging.getLogger(__name__)
POLICY_MONITOR_INTERVAL_SECONDS = 30 * 60


async def _monitor_official_sources():
    """Keep curated official-source cards current even when no browser is open."""
    while True:
        try:
            await asyncio.to_thread(fetch_active_feeds, "policy_listing")
            await asyncio.to_thread(fetch_active_feeds, "official_watch")
            await asyncio.to_thread(fetch_active_feeds, "committee_json")
        except Exception:
            logger.exception("Policy-design source monitoring failed")
        await asyncio.sleep(POLICY_MONITOR_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    monitor_task = asyncio.create_task(_monitor_official_sources())
    try:
        yield
    finally:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass


class NoStaticCacheMiddleware(BaseHTTPMiddleware):
    """Avoid stale CSS/JS in the browser during local development."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response


app = FastAPI(title="infoFeeder Web", debug=True, lifespan=lifespan)
app.add_middleware(NoStaticCacheMiddleware)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.include_router(articles.router)
app.include_router(map.router)
app.include_router(sources.router)


@app.get("/health")
def health():
    return {"ok": True}
