from pathlib import Path


VERSION_FILE = Path(__file__).with_name("VERSION")


def read_app_version():
    """Return the current semver from VERSION (read from disk each call)."""
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip() or "0.0.0"
    except FileNotFoundError:
        return "0.0.0"
