from pathlib import Path

import jinja2
from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
_templates_dir = BASE_DIR / "templates"
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_templates_dir)),
    autoescape=jinja2.select_autoescape(),
    auto_reload=True,
)
templates = Jinja2Templates(env=_jinja_env)
