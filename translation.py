import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


# Reuses the same local Claude CLI binary as claude_generator.py, but this
# module never re-fetches article HTML: it only translates the title/summary
# text that is already in the DB, so the call is much lighter and the
# timeout can be shorter.
CLAUDE_CMD_PATH = Path(
    r"D:\Tools\claude-code\node_modules\@anthropic-ai\claude-code\bin\claude.exe"
)
CLAUDE_TRANSLATE_TIMEOUT_SECONDS = 60

PROMPT_TEMPLATE = """あなたは翻訳アシスタントです。次の記事タイトルと要約を、自然で正確な日本語に直訳してください。

厳守条件:
- 与えられたタイトルと要約の内容だけを翻訳してください。要約や感想、説明、前置きを追加しないでください。
- 固有名詞・数値・単位はできるだけ正確に保持してください。
- 要約が空の場合は、SUMMARY行の値も空のままにしてください。
- 出力は下のテンプレートの2行だけを、そのままの形式で返してください。他の文章は一切書かないでください。

出力テンプレート:
TITLE: <翻訳後のタイトル>
SUMMARY: <翻訳後の要約>

翻訳対象のタイトル: {title}
翻訳対象の要約: {summary}
"""

_TITLE_LINE_RE = re.compile(r"(?m)^TITLE:[ \t]*(.*)$")
_SUMMARY_LINE_RE = re.compile(r"(?m)^SUMMARY:[ \t]*(.*)$")


@dataclass
class TranslationResult:
    ok: bool
    title_ja: str
    summary_ja: str
    error: str


def _build_prompt(title: str, summary: str) -> str:
    return PROMPT_TEMPLATE.format(title=title or "", summary=summary or "")


def _parse_translation_output(stdout_text: str):
    """Parse the strict TITLE:/SUMMARY: two-line output.

    Returns (title_ja, summary_ja) or (None, None) if TITLE could not be
    found at all (treated as a parse failure by the caller).
    """
    title_match = _TITLE_LINE_RE.search(stdout_text)
    if not title_match:
        return None, None

    title_ja = title_match.group(1).strip()
    summary_match = _SUMMARY_LINE_RE.search(stdout_text)
    summary_ja = summary_match.group(1).strip() if summary_match else ""
    return title_ja, summary_ja


def translate_title_summary(title: str, summary: str) -> TranslationResult:
    title = (title or "").strip()
    summary = (summary or "").strip()

    if not title:
        return TranslationResult(False, "", "", "Translation skipped: title was empty.")

    if not CLAUDE_CMD_PATH.exists():
        return TranslationResult(
            False, "", "", f"Translation skipped: Claude CLI was not found at {CLAUDE_CMD_PATH}."
        )

    try:
        completed = subprocess.run(
            [str(CLAUDE_CMD_PATH), "-p", _build_prompt(title, summary)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=CLAUDE_TRANSLATE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return TranslationResult(False, "", "", "Translation skipped: Claude CLI timed out.")
    except Exception as error:
        return TranslationResult(False, "", "", f"Translation skipped: {error}")

    stdout_text = (completed.stdout or "").strip()
    stderr_text = (completed.stderr or "").strip()

    if completed.returncode != 0:
        detail = stderr_text or stdout_text or f"Claude CLI exited with code {completed.returncode}."
        return TranslationResult(False, "", "", f"Translation skipped: {detail}")

    if not stdout_text:
        return TranslationResult(False, "", "", "Translation skipped: Claude CLI returned no text.")

    title_ja, summary_ja = _parse_translation_output(stdout_text)
    if title_ja is None:
        return TranslationResult(False, "", "", "Translation skipped: failed to parse Claude CLI output.")
    if not title_ja:
        return TranslationResult(False, "", "", "Translation skipped: translated title was empty.")

    return TranslationResult(True, title_ja, summary_ja, "")
