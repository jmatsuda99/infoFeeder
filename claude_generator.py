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

PROMPT_TEMPLATE = """あなたは記事要約アシスタントです。
ユーザーから「記事タイトル＋URL」が入力されたら、以下のルールに厳密に従って要約してください。

■ 入力形式
記事タイトル＋URL＋取得できた記事本文

記事タイトル: {title}
URL: {url}

記事本文:
{article_text}

■ 出力形式
以下の順番で、純テキストのみで出力してください。
タイトル（太字）
要約（再構成）
日本語
1〜2文
原文内容に完全準拠
箇条書き
3点
内容・背景・影響などを簡潔に整理
#タグ
英語で3つ
URL
フルリンクを1行のみで記載

■ 厳守条件
記事本文が確認できた場合のみ要約してください。
記事本文を確認できない場合は、要約せず、理由を明記して停止してください。
要約は、上記の確認できた記事本文に完全に準拠してください。
推測、補完、一般知識の混入は禁止です。
表現の再構成は可能ですが、意味の改変は禁止です。
元記事内で一次情報、公式発表、企業リリースなどが特定できる場合は、一次ソースを優先してください。
一次ソースを確認できる場合は、その一次ソースを基準に要約してください。
その場合、出力するURLも一次ソースのURLへ置き換えてください。
情報の純度を重視し、意見、解釈、余計な文脈は一切加えないでください。
バッチ、出典ラベル、媒体名表示は禁止です。
「下野新聞デジタル」などのUIバッジ、出典タグ、媒体タグは出力しないでください。
リンクはURL欄の1行のみとしてください。
カード表示、プレビュー、装飾リンクは禁止です。
出力は純テキストのみで構成してください。
余計なUI要素、メタ情報、説明文は一切出力しないでください。

■ 出力テンプレート
**タイトル**

要約本文。
必要に応じて2文目。

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
        content_type = response.headers.get_content_charset() or "utf-8"
    html_text = raw_bytes.decode(content_type, errors="replace")
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
