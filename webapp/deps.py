import re
from html import escape
from pathlib import Path

import jinja2
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

BASE_DIR = Path(__file__).resolve().parent
_templates_dir = BASE_DIR / "templates"
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_templates_dir)),
    autoescape=jinja2.select_autoescape(),
    auto_reload=True,
)


def _format_overview_inline(text: str) -> str:
    escaped = escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(
        r"(https?://[^\s<]+)",
        r'<a href="\1" target="_blank" rel="noreferrer">\1</a>',
        escaped,
    )
    return escaped


def format_generated_overview(text: str) -> Markup:
    value = (text or "").strip()
    if not value:
        return Markup("")

    blocks = []
    list_items = []

    def flush_list():
        nonlocal list_items
        if not list_items:
            return
        items_html = "".join(f"<li>{item}</li>" for item in list_items)
        blocks.append(f"<ul>{items_html}</ul>")
        list_items = []

    for raw_line in value.splitlines():
        line = raw_line.strip()
        if not line:
            flush_list()
            continue
        if line.startswith("- "):
            list_items.append(_format_overview_inline(line[2:]))
            continue
        flush_list()
        blocks.append(f"<p>{_format_overview_inline(line)}</p>")

    flush_list()
    return Markup("".join(blocks))


_jinja_env.filters["format_generated_overview"] = format_generated_overview
templates = Jinja2Templates(env=_jinja_env)
