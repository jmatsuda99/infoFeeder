# infoFeeder

`infoFeeder` is a local news/source tracking tool built around Google Alerts, RSS/Atom feeds, and simple HTML listing sources.

The repository currently contains two UIs:

- `Streamlit` app: legacy UI, still available
- `FastAPI + HTMX` web app: newer prototype focused on partial updates and better interaction performance

## Current Recommendation

Use the `FastAPI + HTMX` app first.

- URL: `http://127.0.0.1:8510`
- Main pages:
  - `Articles`
  - `Sources`

The Streamlit app is still available at `http://localhost:8502`, but the web app is the active direction for UI changes.

## Features

- Add sources from direct RSS/Atom URLs
- Detect RSS vs HTML listing sources from a base URL
- Group duplicate articles by primary-source URL
- Mark grouped articles as read
- Save / unsave articles
- Open article detail panels
- Copy article title + URL to the clipboard
- Manage sources from the `Sources` page
- Show application version in the web UI

## Run

Use the repository `.venv`.

Install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### FastAPI + HTMX app

Start:

```powershell
.\.venv\Scripts\python.exe run_web.py
```

Open:

```text
http://127.0.0.1:8510
```

### Streamlit app

Start:

```powershell
.\.venv\Scripts\python.exe launcher.py open
```

Open:

```text
http://localhost:8502
```

## Main Files

- [`app.py`](./app.py)
  - Streamlit entry point
- [`articles_view.py`](./articles_view.py)
  - Streamlit article list UI
- [`source_setup_view.py`](./source_setup_view.py)
  - Streamlit source management UI
- [`summary_view.py`](./summary_view.py)
  - Streamlit summary metrics UI
- [`db.py`](./db.py)
  - SQLite access and persistence helpers
- [`fetcher.py`](./fetcher.py)
  - Feed fetching, source detection, article insertion
- [`article_utils.py`](./article_utils.py)
  - URL normalization, grouping keys, copy text helpers
- [`webapp/main.py`](./webapp/main.py)
  - FastAPI application
- [`webapp/templates/`](./webapp/templates)
  - Jinja templates for the web UI
- [`webapp/static/app.css`](./webapp/static/app.css)
  - Web UI styling
- [`run_web.py`](./run_web.py)
  - FastAPI launcher

## Data

SQLite database:

- [`data/alerts.db`](./data/alerts.db)

Other runtime files:

- `data/fetch.lock`
- `streamlit.out.log`
- `streamlit.err.log`

## Dependencies

Current `requirements.txt` includes:

- `streamlit`
- `feedparser`
- `pandas`
- `fastapi`
- `uvicorn`
- `jinja2`
- `python-multipart`

## Notes

- Article grouping is based on normalized primary-source URLs when available.
- The web prototype is intended to reduce the full-page rerun limitations of Streamlit.
- Source management has already been restored in the web UI.
- Further migration work can move more behavior from Streamlit into `webapp/`.
