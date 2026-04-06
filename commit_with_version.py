import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent


def run_git(*args):
    return subprocess.run(["git", *args], cwd=ROOT_DIR, check=True)


def main():
    if len(sys.argv) < 2:
        raise SystemExit("Usage: commit_with_version.py <commit message>")

    message = " ".join(arg.strip() for arg in sys.argv[1:]).strip()
    if not message:
        raise SystemExit("Commit message must not be empty.")

    # VERSION is bumped by .githooks/post-commit (scripts/post_commit_version.py).
    run_git("commit", "-m", message)


if __name__ == "__main__":
    main()
