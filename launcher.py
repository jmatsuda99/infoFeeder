import os
import subprocess
import sys
from launcher_config import (
    PYTHON_EXE,
    ROOT_DIR,
    WEB_ARGS,
    WEB_PORT,
    WEB_READY_URL,
    WEB_STDERR_LOG,
    WEB_STDOUT_LOG,
    WEB_URL,
)
from launcher_runtime import ensure_environment, launch_and_open


def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "open-web"
    if command == "open":
        command = "open-web"

    if command == "open-web":
        launch_and_open(
            port=WEB_PORT,
            app_url=WEB_URL,
            args=WEB_ARGS,
            stdout_log_path=WEB_STDOUT_LOG,
            stderr_log_path=WEB_STDERR_LOG,
            app_name="Web app",
            ready_url=WEB_READY_URL,
            extra_env={"INFOFEEDER_RELOAD": "0"},
        )
        return

    if command == "open-web-dev":
        launch_and_open(
            port=WEB_PORT,
            app_url=WEB_URL,
            args=WEB_ARGS,
            stdout_log_path=WEB_STDOUT_LOG,
            stderr_log_path=WEB_STDERR_LOG,
            app_name="Web app (dev reload)",
            ready_url=WEB_READY_URL,
            extra_env={"INFOFEEDER_RELOAD": "1"},
        )
        return

    if command == "serve-web":
        ensure_environment()
        env = os.environ.copy()
        env["INFOFEEDER_RELOAD"] = "0"
        subprocess.run([str(PYTHON_EXE), *WEB_ARGS], cwd=str(ROOT_DIR), check=True, env=env)
        return

    if command == "serve-web-dev":
        ensure_environment()
        env = os.environ.copy()
        env["INFOFEEDER_RELOAD"] = "1"
        subprocess.run([str(PYTHON_EXE), *WEB_ARGS], cwd=str(ROOT_DIR), check=True, env=env)
        return

    raise SystemExit(f"Unsupported command: {command}. Use: open-web | open-web-dev | serve-web | serve-web-dev")


if __name__ == "__main__":
    main()
