import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

from launcher_config import (
    CHROME_CANDIDATE_PATHS,
    EDGE_CANDIDATE_PATHS,
    PYTHON_EXE,
    ROOT_DIR,
    WAIT_INTERVAL_SECONDS,
    WAIT_TIMEOUT_SECONDS,
    WEB_APP_PATH,
)


def ensure_environment():
    if not PYTHON_EXE.exists():
        raise FileNotFoundError("Python virtual environment was not found at .venv\\Scripts\\python.exe")
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


def start_background_server(args, stdout_log_path, stderr_log_path, extra_env=None):
    creationflags = 0
    if sys.platform.startswith("win"):
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    with stdout_log_path.open("a", encoding="utf-8") as stdout_handle, stderr_log_path.open(
        "a", encoding="utf-8"
    ) as stderr_handle:
        env = os.environ.copy()
        if extra_env:
            env.update(extra_env)
        subprocess.Popen(
            [str(PYTHON_EXE), *args],
            cwd=str(ROOT_DIR),
            stdout=stdout_handle,
            stderr=stderr_handle,
            creationflags=creationflags,
            close_fds=True,
            env=env,
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


def find_edge_executable():
    for edge_path in EDGE_CANDIDATE_PATHS:
        if edge_path.exists():
            return edge_path
    return None


def open_browser(app_url):
    chrome_executable = find_chrome_executable()
    if chrome_executable is not None:
        subprocess.Popen([str(chrome_executable), "--new-tab", app_url], cwd=str(ROOT_DIR), shell=False)
        return
    edge_executable = find_edge_executable()
    if edge_executable is not None:
        subprocess.Popen([str(edge_executable), "--new-tab", app_url], cwd=str(ROOT_DIR), shell=False)
        return
    webbrowser.open(app_url, new=2)


def launch_and_open(
    *,
    port,
    app_url,
    args,
    stdout_log_path,
    stderr_log_path,
    app_name,
    ready_url=None,
    extra_env=None,
):
    ensure_environment()
    ready_url = ready_url or app_url
    if is_server_ready(ready_url):
        open_browser(app_url)
        return

    existing_pid = get_listening_pid(port)
    if existing_pid:
        stop_process(existing_pid)
        wait_for_port_release(port)

    start_background_server(args, stdout_log_path, stderr_log_path, extra_env=extra_env)
    if not wait_for_server(ready_url):
        raise RuntimeError(f"{app_name} did not become ready within {WAIT_TIMEOUT_SECONDS} seconds.")
    open_browser(app_url)
