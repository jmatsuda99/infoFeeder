import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
PYTHON_EXE = ROOT_DIR / ".venv" / "Scripts" / "python.exe"

CHROME_CANDIDATE_PATHS = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "Application" / "chrome.exe",
]
EDGE_CANDIDATE_PATHS = [
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    / "Microsoft"
    / "Edge"
    / "Application"
    / "msedge.exe",
]

WEB_APP_PATH = ROOT_DIR / "run_web.py"
WEB_PORT = 8510
WEB_URL = f"http://127.0.0.1:{WEB_PORT}"
WEB_READY_URL = f"{WEB_URL}/health"
WEB_ARGS = [str(WEB_APP_PATH)]
WEB_STDOUT_LOG = ROOT_DIR / "webapp_stdout.log"
WEB_STDERR_LOG = ROOT_DIR / "webapp_stderr.log"

WAIT_TIMEOUT_SECONDS = 30
WAIT_INTERVAL_SECONDS = 0.5
