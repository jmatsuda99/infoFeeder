import os


def _env_true(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    import uvicorn

    # Default: stable runtime (no reloader). Use INFOFEEDER_RELOAD=1 for dev.
    reload_enabled = _env_true("INFOFEEDER_RELOAD", default=False)
    uvicorn.run(
        "webapp.main:app",
        host="127.0.0.1",
        port=8510,
        reload=reload_enabled,
    )
