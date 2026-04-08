from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from db import init_db
from webapp.deps import BASE_DIR
from webapp.routes import articles, sources


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


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
app.include_router(sources.router)


@app.get("/health")
def health():
    return {"ok": True}
