import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
PYTHON_EXE = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
APP_PATH = ROOT_DIR / "app.py"
PORT = 8502
APP_URL = f"http://localhost:{PORT}"
STREAMLIT_ARGS = [
    "-m",
    "streamlit",
    "run",
    str(APP_PATH),
    "--server.port",
    str(PORT),
    "--server.headless",
    "true",
]
STDOUT_LOG = ROOT_DIR / "streamlit.out.log"
STDERR_LOG = ROOT_DIR / "streamlit.err.log"
WAIT_TIMEOUT_SECONDS = 30
WAIT_INTERVAL_SECONDS = 0.5


def ensure_environment():
    if not PYTHON_EXE.exists():
        raise FileNotFoundError("Python virtual environment was not found at .venv\\Scripts\\python.exe")
    if not APP_PATH.exists():
        raise FileNotFoundError("app.py was not found in the project root.")


def is_server_ready():
    try:
        with urllib.request.urlopen(APP_URL, timeout=2) as response:
            return 200 <= response.status < 500
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def start_background_server():
    creationflags = 0
    if sys.platform.startswith("win"):
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    with STDOUT_LOG.open("a", encoding="utf-8") as stdout_handle, STDERR_LOG.open("a", encoding="utf-8") as stderr_handle:
        subprocess.Popen(
            [str(PYTHON_EXE), *STREAMLIT_ARGS],
            cwd=str(ROOT_DIR),
            stdout=stdout_handle,
            stderr=stderr_handle,
            creationflags=creationflags,
            close_fds=True,
        )


def wait_for_server(timeout_seconds=WAIT_TIMEOUT_SECONDS):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if is_server_ready():
            return True
        time.sleep(WAIT_INTERVAL_SECONDS)
    return is_server_ready()


def open_browser():
    webbrowser.open(APP_URL)


def launch_and_open():
    ensure_environment()
    if not is_server_ready():
        start_background_server()
        if not wait_for_server():
            raise RuntimeError(f"Streamlit did not become ready within {WAIT_TIMEOUT_SECONDS} seconds.")
    open_browser()


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "open"
    if command == "open":
        launch_and_open()
        return
    if command == "serve":
        ensure_environment()
        subprocess.run([str(PYTHON_EXE), *STREAMLIT_ARGS], cwd=str(ROOT_DIR), check=True)
        return
    raise SystemExit(f"Unsupported command: {command}")


if __name__ == "__main__":
    main()
