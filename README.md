# infoFeeder

`infoFeeder` is a local news/source tracking tool built around Google Alerts, RSS/Atom feeds, and simple HTML listing sources.

The UI is a **FastAPI + HTMX** web app (partial updates, responsive interactions).

- URL: `http://127.0.0.1:8510`
- Main pages: **Articles**, **Sources**

The legacy **Streamlit** UI has been removed; all behavior lives under `webapp/` and shared modules (`db.py`, `fetcher.py`, etc.).

## Version

- The semantic version is stored in the repo-root [`VERSION`](./VERSION) file.
- The web UI reads it on **each request** (no server restart needed after changing `VERSION`).
- Optional: after `.\scripts\setup_git_hooks.ps1`, Git **post-commit** can bump `VERSION` from the commit message (see [`bump_version.py`](./bump_version.py)).

## Features

- Add sources from direct RSS/Atom URLs
- Detect RSS vs HTML listing sources from a base URL
- Group duplicate articles by primary-source URL
- Mark grouped articles as read; save / unsave
- Open article detail panels; copy title + URL to the clipboard
- Manage sources on the **Sources** page
- Show application version in the web UI

## Run

Use the repository **`.venv`**.

Install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Web app

Start (includes **uvicorn `--reload`** for `.py` changes):

```powershell
.\.venv\Scripts\python.exe run_web.py
```

Open:

```text
http://127.0.0.1:8510
```

### Launcher (browser + background server)

Default command (no args) or **`open-web`** starts the web app and opens Chrome/Edge (or the default browser) when ready (**stable mode**, no code reloader):

```powershell
.\.venv\Scripts\python.exe launcher.py
.\.venv\Scripts\python.exe launcher.py open-web
```

**`launcher.py open`** is an alias for **`open-web`** (kept for older scripts). **`start_infofeeder.bat`** calls `open-web`.

Development mode (auto-reload on `.py` changes):

```powershell
.\.venv\Scripts\python.exe launcher.py open-web-dev
```

Foreground server only (no browser):

```powershell
.\.venv\Scripts\python.exe launcher.py serve-web
```

### Desktop shortcut (Windows)

Create **`infoFeeder Web.lnk`** on the desktop (target is `start_infofeeder.vbs`, no console window):

```powershell
.\scripts\create_infofeeder_shortcut.ps1 -Desktop
```

To place the shortcut in the repo folder only, run without `-Desktop`. `*.lnk` is gitignored (paths are machine-specific).

## Main files

| Area | Path |
|------|------|
| SQLite / queries | [`db.py`](./db.py) |
| Fetching / ingestion | [`fetcher.py`](./fetcher.py) |
| URLs / grouping keys | [`article_utils.py`](./article_utils.py) |
| JST time display | [`jst_format.py`](./jst_format.py) |
| Version helper | [`version.py`](./version.py) (`read_app_version()`) |
| Web FastAPI app | [`webapp/main.py`](./webapp/main.py) |
| Web routes | [`webapp/routes/articles.py`](./webapp/routes/articles.py), [`webapp/routes/sources.py`](./webapp/routes/sources.py) |
| Article grouping (web) | [`webapp/article_groups.py`](./webapp/article_groups.py) |
| Jinja templates | [`webapp/templates/`](./webapp/templates) |
| Web CSS | [`webapp/static/app.css`](./webapp/static/app.css) |
| Uvicorn entry | [`run_web.py`](./run_web.py) |
| Windows launcher | [`launcher.py`](./launcher.py), [`launcher_config.py`](./launcher_config.py), [`launcher_runtime.py`](./launcher_runtime.py), [`start_infofeeder.bat`](./start_infofeeder.bat), [`start_infofeeder.vbs`](./start_infofeeder.vbs) |

## Data

SQLite database (local, not committed by default):

- `data/alerts.db`

Other runtime files may include:

- `data/fetch.lock`
- `webapp_stdout.log`, `webapp_stderr.log`

## Dependencies

See [`requirements.txt`](./requirements.txt) (`feedparser`, `pandas`, `fastapi`, `uvicorn`, `jinja2`, `python-multipart`).

## Notes

- Article grouping uses normalized primary-source URLs when available.
- The web app uses **HTMX** for partial page updates (e.g. article list, read/save toggles, scheduled fetch refresh without a full reload).
- Jinja templates use **`auto_reload`** in development; `/static` responses use **no-cache** headers so CSS changes show up after a normal browser refresh.
