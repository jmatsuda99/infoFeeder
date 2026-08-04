import re
import subprocess
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from db import get_article_generation_input, update_article_generated_overview


CLAUDE_CMD_PATH = Path(
    r"D:\Tools\claude-code\node_modules\@anthropic-ai\claude-code\bin\claude.exe"
)
CLAUDE_TIMEOUT_SECONDS = 180
FETCH_TIMEOUT_SECONDS = 20
MAX_ARTICLE_TEXT_CHARS = 16000

PROMPT_TEMPLATE = """あなたは記事要約アシスタントです。与えられた記事本文だけを根拠に、日本語で短く正確に要約してください。

記事タイトル: {title}
URL: {url}

記事本文:
{article_text}

厳守条件:
- 要約は記事本文に書かれている内容だけに基づいてください。
- 推測、補完、一般知識、感想、前置きは禁止です。
- 本文の一部に文字化けがあっても、全体として内容を読み取れるなら通常どおり要約してください。
- エンコーディングや文字化けについては、本文理解が不可能な場合にだけ触れてください。
- 本文理解が不可能な場合は、要約せず「Summary skipped:」で始まる1文だけを返してください。
- 本文理解が可能な場合は、「記事本文を確認しました」や「以下に要約します」などの説明文を書かないでください。
- URLは最後の1行に生のURLだけを書いてください。Markdownリンク形式は禁止です。
- 出力は下のテンプレートに厳密に従ってください。

出力テンプレート:
**タイトル**

1〜2文の要約

- 箇条書き1
- 箇条書き2
- 箇条書き3

#TagOne #TagTwo #TagThree

https://example.com
"""


@dataclass
class ClaudeOverviewResult:
    ok: bool
    overview_text: str
    error_text: str
    source_text: str


def _normalize_article_text(html_text: str) -> str:
    text = re.sub(r"(?is)<script\b.*?</script>", " ", html_text)
    text = re.sub(r"(?is)<style\b.*?</style>", " ", text)
    text = re.sub(r"(?is)<noscript\b.*?</noscript>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = unescape(text)
    text = text.replace("\r", " ")
    text = re.sub(r"[ \t\u3000]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    text = text.strip()
    if len(text) > MAX_ARTICLE_TEXT_CHARS:
        text = text[:MAX_ARTICLE_TEXT_CHARS]
    return text


def _extract_meta_charset(raw_bytes: bytes) -> str:
    head = raw_bytes[:4096]
    match = re.search(br"<meta[^>]+charset=['\"]?\s*([a-zA-Z0-9_\-]+)", head, re.IGNORECASE)
    if match:
        return match.group(1).decode("ascii", errors="ignore").lower()
    match = re.search(
        br"<meta[^>]+content=['\"][^>]*charset=([a-zA-Z0-9_\-]+)",
        head,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).decode("ascii", errors="ignore").lower()
    return ""


def _decode_article_html(raw_bytes: bytes, header_charset: str = "") -> str:
    candidates = []
    for encoding in (
        (header_charset or "").strip().lower(),
        _extract_meta_charset(raw_bytes),
        "utf-8",
        "cp932",
        "shift_jis",
        "euc-jp",
    ):
        if encoding and encoding not in candidates:
            candidates.append(encoding)

    for encoding in candidates:
        try:
            return raw_bytes.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue

    return raw_bytes.decode("utf-8", errors="replace")


def _fetch_article_text(url: str) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            )
        },
    )
    with urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
        raw_bytes = response.read()
        header_charset = response.headers.get_content_charset() or ""
    html_text = _decode_article_html(raw_bytes, header_charset)
    return _normalize_article_text(html_text)


def _build_prompt(title: str, url: str, article_text: str) -> str:
    return PROMPT_TEMPLATE.format(
        title=title or "",
        url=url or "",
        article_text=article_text or "",
    )


def generate_overview_for_article(article_key_value: str) -> ClaudeOverviewResult:
    article = get_article_generation_input(article_key_value)
    if not article:
        return ClaudeOverviewResult(False, "", "Summary skipped: article record was not found.", "")

    title = (article.get("title") or "").strip()
    url = (article.get("link") or "").strip()
    if not url:
        return ClaudeOverviewResult(False, "", "Summary skipped: article URL was not found.", "")

    if not CLAUDE_CMD_PATH.exists():
        return ClaudeOverviewResult(
            False,
            "",
            f"Summary skipped: Claude CLI was not found at {CLAUDE_CMD_PATH}.",
            url,
        )

    try:
        article_text = _fetch_article_text(url)
    except URLError as error:
        return ClaudeOverviewResult(False, "", f"Summary skipped: failed to access article URL ({error}).", url)
    except Exception as error:
        return ClaudeOverviewResult(False, "", f"Summary skipped: failed to parse article URL ({error}).", url)

    if not article_text:
        return ClaudeOverviewResult(False, "", "Summary skipped: article text could not be extracted.", url)

    try:
        completed = subprocess.run(
            [str(CLAUDE_CMD_PATH), "-p", _build_prompt(title, url, article_text)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=CLAUDE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ClaudeOverviewResult(False, "", "Summary skipped: Claude CLI timed out.", url)
    except Exception as error:
        return ClaudeOverviewResult(False, "", f"Summary skipped: {error}", url)

    stdout_text = (completed.stdout or "").strip()
    stderr_text = (completed.stderr or "").strip()

    if completed.returncode != 0:
        detail = stderr_text or stdout_text or f"Claude CLI exited with code {completed.returncode}."
        return ClaudeOverviewResult(False, "", f"Summary skipped: {detail}", url)

    if not stdout_text:
        return ClaudeOverviewResult(False, "", "Summary skipped: Claude CLI returned no text.", url)

    if stdout_text.lower().startswith("summary skipped:"):
        return ClaudeOverviewResult(False, "", stdout_text, url)

    return ClaudeOverviewResult(True, stdout_text, "", url)


def generate_and_store_overview(article_key_value: str) -> ClaudeOverviewResult:
    result = generate_overview_for_article(article_key_value)
    update_article_generated_overview(
        article_key_value,
        result.overview_text,
        result.error_text,
        result.source_text,
    )
    return result
