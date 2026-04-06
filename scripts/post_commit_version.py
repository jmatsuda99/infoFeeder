"""
Bump VERSION after each commit based on the commit message (Conventional Commits-style).

Uses git commit --amend so VERSION is included in the same commit. Merge commits are skipped.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from bump_version import (  # noqa: E402
    VERSION_FILE,
    bump_version,
    detect_bump_level,
    read_version,
    write_version,
)

SKIP_ENV = "INFOFEEDER_SKIP_POST_COMMIT_VERSION"


def _run_git(*args, **kwargs):
    return subprocess.run(["git", *args], cwd=ROOT_DIR, **kwargs)


def _is_merge_commit():
    result = _run_git("rev-parse", "--verify", "HEAD^2", capture_output=True)
    return result.returncode == 0


def _commit_touches_version():
    result = _run_git(
        "diff-tree",
        "--no-commit-id",
        "--name-only",
        "-r",
        "HEAD",
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False
    return any(name.strip() == "VERSION" for name in result.stdout.splitlines())


def main():
    if os.environ.get(SKIP_ENV):
        return 0
    if _run_git("rev-parse", "--git-dir", capture_output=True).returncode != 0:
        return 0
    if _is_merge_commit():
        return 0
    if _commit_touches_version():
        return 0

    msg_result = _run_git("log", "-1", "--pretty=%B", capture_output=True, text=True)
    if msg_result.returncode != 0:
        return 0
    message = msg_result.stdout or ""

    current = read_version()
    next_version = bump_version(current, detect_bump_level(message))

    write_version(next_version)
    add_result = _run_git("add", str(VERSION_FILE.relative_to(ROOT_DIR)))
    if add_result.returncode != 0:
        return add_result.returncode

    env = os.environ.copy()
    env[SKIP_ENV] = "1"
    amend = _run_git(
        "commit",
        "--amend",
        "--no-edit",
        "--no-verify",
        env=env,
    )
    return amend.returncode


if __name__ == "__main__":
    raise SystemExit(main())
