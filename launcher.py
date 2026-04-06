import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
PYTHON_EXE = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
CHROME_CANDIDATE_PATHS = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "Application" / "chrome.exe",
]
STREAMLIT_APP_PATH = ROOT_DIR / "app.py"
STREAMLIT_PORT = 8502
STREAMLIT_URL = f"http://localhost:{STREAMLIT_PORT}"
STREAMLIT_ARGS = [
    "-m",
    "streamlit",
    "run",
    str(STREAMLIT_APP_PATH),
    "--server.port",
    str(STREAMLIT_PORT),
    "--server.headless",
    "true",
]
STREAMLIT_STDOUT_LOG = ROOT_DIR / "streamlit.out.log"
STREAMLIT_STDERR_LOG = ROOT_DIR / "streamlit.err.log"
WEB_APP_PATH = ROOT_DIR / "run_web.py"
WEB_PORT = 8510
WEB_URL = f"http://127.0.0.1:{WEB_PORT}"
WEB_ARGS = [str(WEB_APP_PATH)]
WEB_STDOUT_LOG = ROOT_DIR / "webapp_stdout.log"
WEB_STDERR_LOG = ROOT_DIR / "webapp_stderr.log"
WAIT_TIMEOUT_SECONDS = 30
WAIT_INTERVAL_SECONDS = 0.5


def ensure_environment():
    if not PYTHON_EXE.exists():
        raise FileNotFoundError("Python virtual environment was not found at .venv\\Scripts\\python.exe")
    if not STREAMLIT_APP_PATH.exists():
        raise FileNotFoundError("app.py was not found in the project root.")
    if not WEB_APP_PATH.exists():
        raise FileNotFoundError("run_web.py was not found in the project root.")


def is_server_ready(app_url):
    try:
        with urllib.request.urlopen(app_url, timeout=2) as response:
            return 200 <= response.status < 500
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def get_listening_pid(port):
    try:
        completed = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    port_suffix = f":{port}"
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        if parts[1].endswith(port_suffix) and parts[3].upper() == "LISTENING":
            try:
                return int(parts[4])
            except ValueError:
                return None
    return None


def stop_process(pid):
    if not pid:
        return
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/F", "/T"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def wait_for_port_release(port, timeout_seconds=WAIT_TIMEOUT_SECONDS):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if get_listening_pid(port) is None:
            return True
        time.sleep(WAIT_INTERVAL_SECONDS)
    return get_listening_pid(port) is None


def start_background_server(args, stdout_log_path, stderr_log_path):
    creationflags = 0
    if sys.platform.startswith("win"):
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    with stdout_log_path.open("a", encoding="utf-8") as stdout_handle, stderr_log_path.open("a", encoding="utf-8") as stderr_handle:
        subprocess.Popen(
            [str(PYTHON_EXE), *args],
            cwd=str(ROOT_DIR),
            stdout=stdout_handle,
            stderr=stderr_handle,
            creationflags=creationflags,
            close_fds=True,
        )


def wait_for_server(app_url, timeout_seconds=WAIT_TIMEOUT_SECONDS):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if is_server_ready(app_url):
            return True
        time.sleep(WAIT_INTERVAL_SECONDS)
    return is_server_ready(app_url)


def find_chrome_executable():
    for chrome_path in CHROME_CANDIDATE_PATHS:
        if chrome_path.exists():
            return chrome_path
    return None


def open_browser(app_url):
    chrome_executable = find_chrome_executable()
    if chrome_executable is not None:
        subprocess.Popen([str(chrome_executable), "--new-tab", app_url], cwd=str(ROOT_DIR))
        return
    webbrowser.open(app_url)


def launch_and_open(*, port, app_url, args, stdout_log_path, stderr_log_path, app_name):
    ensure_environment()
    existing_pid = get_listening_pid(port)
    if existing_pid:
        stop_process(existing_pid)
        wait_for_port_release(port)

    start_background_server(args, stdout_log_path, stderr_log_path)
    if not wait_for_server(app_url):
        raise RuntimeError(f"{app_name} did not become ready within {WAIT_TIMEOUT_SECONDS} seconds.")
    open_browser(app_url)


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "open-web"
    if command == "open":
        launch_and_open(
            port=STREAMLIT_PORT,
            app_url=STREAMLIT_URL,
            args=STREAMLIT_ARGS,
            stdout_log_path=STREAMLIT_STDOUT_LOG,
            stderr_log_path=STREAMLIT_STDERR_LOG,
            app_name="Streamlit",
        )
        return
    if command == "serve":
        ensure_environment()
        subprocess.run([str(PYTHON_EXE), *STREAMLIT_ARGS], cwd=str(ROOT_DIR), check=True)
        return
    if command == "open-web":
        launch_and_open(
            port=WEB_PORT,
            app_url=WEB_URL,
            args=WEB_ARGS,
            stdout_log_path=WEB_STDOUT_LOG,
            stderr_log_path=WEB_STDERR_LOG,
            app_name="Web app",
        )
        return
    if command == "serve-web":
        ensure_environment()
        subprocess.run([str(PYTHON_EXE), *WEB_ARGS], cwd=str(ROOT_DIR), check=True)
        return
    raise SystemExit(f"Unsupported command: {command}")


if __name__ == "__main__":
    main()
