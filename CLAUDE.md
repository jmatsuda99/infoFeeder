# CLAUDE.md

Guidance for working on infoFeeder, distilled from a work session that expanded source coverage and rebuilt article filtering/classification.

## Running the app

- Web UI: `.venv/Scripts/python.exe run_web.py`. Despite what README says (8510), the server in this environment actually listens on **port 8512** — check `run_web_stdout.log` for the real `Uvicorn running on http://127.0.0.1:...` line before assuming a port.
- `init_db()` (in `db.py`) runs on every startup and re-seeds/re-backfills curated sources, `topic_category`, and `is_noise` for any row whose computed value differs from what's stored. It's a full-table pass but cheap (regex/dict lookups only) — expect ~1-2s for ~14k rows. It does **not** run translation or PDF extraction (those are separate, deliberately not baked into startup because they shell out to an external CLI/parse binaries and would make every restart slow).
- The repo has a **post-commit hook** that auto-bumps `VERSION` and amends it into the commit. It prints a `UnicodeDecodeError` from a reader thread to stderr on every commit — this is harmless/cosmetic, not a real failure; check `git log`/`git show --stat HEAD` to confirm the commit actually succeeded (it does, with VERSION included).

## Article pipeline

`fetcher.py` → `classify_article()` (`category_classifier.py`) → `is_noise_article()` (`noise_filter.py`) → optional `translate_title_summary()` (`translation.py`) → INSERT. All four steps run per-row inside `insert_feed_rows()`, and are re-run in `db.py`'s `init_db()` backfill loop for existing rows whenever their logic changes. When adding a new per-article computation, follow this same pattern: compute in both places, only `UPDATE` when the value actually differs.

### Source curation (`policy_sources.py`)

Six tuples define **curated, single-purpose feeds** that are structurally trusted — every article from them is assumed on-topic regardless of content:
`POLICY_DESIGN_SOURCES`, `OFFICIAL_WATCH_SOURCES`, `COMMITTEE_WATCH_SOURCES`, `UTILITY_RSS_SOURCES`, `RESEARCH_RSS_SOURCES`, `INTERNATIONAL_RSS_SOURCES`. Their URLs are collected into `noise_filter.CURATED_FEED_URLS`, checked first in `is_noise_article()` before any keyword logic runs. Anything **not** in these tuples (Google Alerts, or feeds added ad hoc via the Sources UI) gets full content-based scrutiny. When registering a new official/institutional source, prefer adding it to one of these tuples over letting it default to generic `html_listing` — untrusted sources with terse titles (e.g. "第100回...") get misclassified as noise.

### Category classification (`category_classifier.py`)

`classify_article(title, summary, feed_category, source_type)`: if `feed_category` is a key in `LEGACY_FEED_CATEGORY_MAP`, that mapping wins outright (used for feeds where "which company/region this is from" *is* the category, e.g. 事業者動向, 国際動向 — every article from an EIA/IEA/utility-company feed gets that label regardless of content). Otherwise it scores `KEYWORD_CATEGORY_MAP` keywords, weighting title matches over summary matches, preferring Google Alerts' `<b>...</b>` highlight terms when present (`extract_bold_terms()` in `article_utils.py`).

Two opposite design intents coexist by category:
- **事業者動向 / 国際動向** (and similar "this whole feed is the same story" categories): feed-level category is trusted — don't add these to `LEGACY_FEED_CATEGORY_MAP` unless every article from that feed really should get one label.
- **Research institutes** (CRIEPI, RITE, etc.): deliberately *not* added to `LEGACY_FEED_CATEGORY_MAP` even though they're curated, because one institute's releases span many topics — each article gets its own per-content classification instead.

### Noise filtering (`noise_filter.py`)

Layered, in this order: curated-source bypass → domain blocklist (market-research spam, investor-commentary sites) → domain+path patterns (blocks only specific accounts/paths on otherwise-legit domains, e.g. one `note.com` contributor) → title/summary regex patterns (market-report boilerplate, ESG-declaration-only announcements) → keyword retention → default noise.

Retention keywords are split `STRONG_RETAIN_KEYWORDS` (sufficient alone) vs `WEAK_RETAIN_KEYWORDS` (generic terms like 委員会/審議会/需給/料金 that also appear in non-power contexts — these no longer retain on their own).

**"Power situation" scope is being narrowed in stages, per-category, not applied uniformly.** A blanket "must reference storage/trading/grid/tariff/institutional terms" rule would reclassify ~61% of currently-kept articles as noise (verified by simulation), gutting renewables/decarbonization/hydrogen/nuclear/EV/international coverage that the project spent significant effort building up. So:
- `SYSTEM_ANCHOR_KEYWORDS` + `SYSTEM_ANCHOR_SCOPE_CATEGORIES` (制度設計/電力市場/事業者動向): narrow anchor set (storage/trading/grid/tariff/institutional/utility names).
- `POWER_GENERATION_ANCHOR_KEYWORDS` + `POWER_GENERATION_ANCHOR_SCOPE_CATEGORIES` (脱炭素・カーボンニュートラル): wider anchor set that also accepts generation/procurement specifics (発電, PPA, 太陽光発電所, kWh, etc.) since blanket-applying the narrow set here would remove ~90% of the category.
- Other categories (再生可能エネルギー, 水素・アンモニア, 火力・化石燃料, 原子力, EV・モビリティ, データセンター・AI電力, 国際動向) are **not yet in scope** for this narrowing — their existing `STRONG_RETAIN_KEYWORDS` logic is untouched. Don't assume the anchor-keyword pattern applies there without checking `*_SCOPE_CATEGORIES` first.

Known sharp edges when adding new keywords: avoid bare single-character-adjacent terms like standalone "電気"/"電力" (they substring-match inside unrelated compounds like 電気自動車); avoid negation-insensitive terms like bare "原発"/"原子力" without also handling 反/脱-prefixed political-stance mentions (see `_OPPOSITION_PHRASE_RE`).

### Translation (`translation.py`)

Only applies to non-Japanese `title`/`summary` (`is_non_japanese_text()` in `article_utils.py` — no Japanese-script characters present). Overwrites `title`/`summary` in place (no separate "original" column). For `official_watch`/`policy_listing` sources whose extracted title is prefixed with the Japanese feed name (e.g. `"IEA（国際エネルギー機関）: <English title>"`), `split_source_name_prefix()` must strip that prefix before the language check/translation, or the whole title reads as "already Japanese" and gets skipped — this bit IEA specifically since its feed name contains kanji.

### PDF article summaries (`claude_generator.py`)

`generate_overview_for_article()` fetches the article URL and summarizes via a local Claude CLI. It sniffs PDF via content-type / `.pdf` suffix / `%PDF-` magic bytes and routes to `pypdf`-based extraction (`_extract_pdf_text()`), including a `decrypt("")` attempt for the print-restricted/owner-password PDFs several official sources (TEPCO, IEEJ, OCCTO) publish. This is a different, lighter-weight extraction than `translation.py` — it re-fetches and parses the full article body, whereas translation only rewrites the already-stored title/summary text.

## Housekeeping

- `data/alerts.db.bak_*` files accumulate from pre-migration safety backups taken during risky schema/backfill changes — not auto-cleaned, safe to delete once a change is verified.
- `.infofeeder.env`, `*.log` at repo root, and `data/*.db*` are working artifacts, not committed — check `git status` before `git add`-ing broadly.
- Claude Code skills installed via `npx skills add` (e.g. `pretty-mermaid`) live under `.agents/`, `.claude/skills/`, and `skills-lock.json` — these are gitignored; install `--global` (`~/.agents/skills/...`) if a skill should be usable across projects rather than just this one.
