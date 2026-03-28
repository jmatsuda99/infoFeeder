import subprocess
import sys
from pathlib import Path

from bump_version import (
    VERSION_FILE,
    bump_version,
    detect_bump_level,
    read_version,
    write_version,
)


ROOT_DIR = Path(__file__).resolve().parent


def run_git(*args):
    return subprocess.run(["git", *args], cwd=ROOT_DIR, check=True)


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: commit_with_version.py <commit message>")

    message = " ".join(arg.strip() for arg in sys.argv[1:]).strip()
    if not message:
        raise SystemExit("Commit message must not be empty.")

    previous_version_text = VERSION_FILE.read_text(encoding="utf-8")
    previous_version = read_version()
    next_version = bump_version(previous_version, detect_bump_level(message))

    try:
        write_version(next_version)
        run_git("add", "VERSION")
        run_git("commit", "-m", message)
    except subprocess.CalledProcessError:
        VERSION_FILE.write_text(previous_version_text, encoding="utf-8")
        run_git("add", "VERSION")
        raise


if __name__ == "__main__":
    main()
