from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from webapp.deps import BASE_DIR
from webapp.routes import articles, sources

app = FastAPI(title="infoFeeder Web", debug=True)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.include_router(articles.router)
app.include_router(sources.router)


@app.get("/health")
def health():
    return {"ok": True}
