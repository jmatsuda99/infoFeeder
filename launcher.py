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
POWERSHELL_EXE = "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe"


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


def get_listening_pid():
    try:
        completed = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    port_suffix = f":{PORT}"
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


def get_process_details(pid):
    if not pid or not sys.platform.startswith("win"):
        return None

    command = (
        f"$p = Get-CimInstance Win32_Process -Filter \"ProcessId = {pid}\"; "
        "if ($p) { "
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "Write-Output ($p.ExecutablePath); "
        "Write-Output ($p.CommandLine) }"
    )
    try:
        completed = subprocess.run(
            [POWERSHELL_EXE, "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    lines = [line.strip() for line in completed.stdout.splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        return None
    executable_path = lines[0]
    command_line = "\n".join(lines[1:]) if len(lines) > 1 else ""
    return {"executable_path": executable_path, "command_line": command_line}


def normalize_path(value):
    try:
        return str(Path(value).resolve()).casefold()
    except (OSError, RuntimeError, TypeError):
        return str(value).casefold()


def is_expected_listener(pid):
    details = get_process_details(pid)
    if not details:
        return False

    executable_path = details.get("executable_path") or ""
    command_line = details.get("command_line") or ""
    if normalize_path(executable_path) != normalize_path(PYTHON_EXE):
        return False
    return str(APP_PATH).casefold() in command_line.casefold()


def stop_process(pid):
    if not pid:
        return
    subprocess.run(
        ["taskkill", "/PID", str(pid), "/F", "/T"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def wait_for_port_release(timeout_seconds=WAIT_TIMEOUT_SECONDS):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if get_listening_pid() is None:
            return True
        time.sleep(WAIT_INTERVAL_SECONDS)
    return get_listening_pid() is None


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
    existing_pid = get_listening_pid()
    if existing_pid:
        if is_expected_listener(existing_pid):
            if not wait_for_server():
                stop_process(existing_pid)
                wait_for_port_release()
        else:
            stop_process(existing_pid)
            wait_for_port_release()

    if get_listening_pid() is None:
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
