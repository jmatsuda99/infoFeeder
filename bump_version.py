from pathlib import Path
import re
import sys


ROOT_DIR = Path(__file__).resolve().parent
VERSION_FILE = ROOT_DIR / "VERSION"

PATCH_TYPES = {"fix", "refactor", "perf", "docs", "style", "test", "chore"}
MINOR_TYPES = {"feat"}


def read_version():
    raw = VERSION_FILE.read_text(encoding="utf-8").strip()
    parts = raw.split(".")
    if len(parts) != 3 or not all(part.isdigit() for part in parts):
        raise ValueError(f"Unsupported version format: {raw}")
    return [int(part) for part in parts]


def write_version(version_parts):
    VERSION_FILE.write_text(".".join(str(part) for part in version_parts) + "\n", encoding="utf-8")


def detect_bump_level(message):
    normalized = message.strip()
    if not normalized:
        return "patch"

    lower_message = normalized.lower()
    if "breaking change" in lower_message:
        return "major"

    first_line = normalized.splitlines()[0].strip()
    match = re.match(r"^(?P<type>[a-z]+)(\([^)]+\))?(?P<breaking>!)?:", first_line, re.IGNORECASE)
    if not match:
        return "patch"

    commit_type = match.group("type").lower()
    if match.group("breaking"):
        return "major"
    if commit_type in MINOR_TYPES:
        return "minor"
    if commit_type in PATCH_TYPES:
        return "patch"
    return "patch"


def bump_version(version_parts, level):
    major, minor, patch = version_parts
    if level == "major":
        return [major + 1, 0, 0]
    if level == "minor":
        return [major, minor + 1, 0]
    return [major, minor, patch + 1]


def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: bump_version.py <commit_message_file>")

    commit_message_path = Path(sys.argv[1])
    message = commit_message_path.read_text(encoding="utf-8")
    current_version = read_version()
    next_version = bump_version(current_version, detect_bump_level(message))
    write_version(next_version)


if __name__ == "__main__":
    main()
