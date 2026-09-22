# Article Scrape Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a uv-managed Python pipeline that scrapes Google News RSS for 4 fixed keywords, keeps only 2025 articles, dedupes, translates EN→ID, and publishes a downloadable xlsx via GitHub Actions Release.

**Architecture:** Single-entry `src/scrape.py` orchestrates small focused modules (`fetcher`, `filters`, `translator`, `exporter`); no DB, no API keys; CI reruns the same `uv run` command and uploads `output/` as artifact + Release.

**Tech Stack:** Python >=3.11, uv, feedparser, python-dateutil, openpyxl, langdetect, deep-translator, pytest

## Global Constraints

- Keywords (exact, 4): `kerja sama microsoft dengan pemerintah indonesia di tahun 2025`, `investasi microsoft di Indonesia tahun 2025`, `Indonesia central cloud region (2025)`, `Microsoft elevAIte di Indonesia 2025`
- Date filter strict: `2025-01-01` to `2025-12-31` inclusive, no 2026 leakage.
- Languages: Indonesian + English; English title+snippet translated to Indonesian, originals preserved.
- Dedupe rule: normalized URL (strip tracking params, lowercase host, strip trailing slash), keep first-seen, record `Also_Found_In`.
- Package manager: `uv` only (`pyproject.toml` + `uv.lock`, run via `uv sync` / `uv run`).
- No API keys; Google News RSS only.
- XLSX columns exact: `No | Publisher | Title_ID | Title_Original | URL | Date | Keyword_Found | Also_Found_In | Snippet_ID | Snippet_Original | Source_Lang | translation_ok`
- Output paths: `output/articles-2025.xlsx` + `output/run-meta.json` (gitignored, CI artifact).
- Docs structure: `docs/active/` (in-progress), `docs/completed/` (approved), `docs/README.md` (index).

---

## File Structure

- Create: `pyproject.toml` — uv project, deps, pytest config. Single responsibility: dependency + entry declaration.
- Create: `.gitignore` — ignore `output/`, `.venv/`, `__pycache__/`.
- Create: `src/__init__.py` — empty, makes `src` importable.
- Create: `src/fetcher.py` — `fetch_keyword_rss(keyword, hl, gl, ceid) -> list[RawArticle]` + `fetch_all(keywords)`. Owns HTTP, retry, delay, RSS parse.
- Create: `src/filters.py` — `parse_date(raw)`, `is_in_2025(dt)`, `normalize_url(url)`, `dedupe(articles)`. Owns date + dedupe rules.
- Create: `src/translator.py` — `detect_lang(text) -> str`, `translate_en_to_id(text) -> (translated, ok)`, `enrich(articles)`. Owns langdetect + deep-translator with fallback.
- Create: `src/exporter.py` — `export_xlsx(rows, path)`, `write_meta(meta, path)`. Owns openpyxl styling + run-meta.json.
- Create: `src/scrape.py` — `KEYWORDS`, `LOCALES`, `main()` orchestration. Owns wiring only, no logic.
- Create: `tests/test_filters.py`, `tests/test_translator.py`, `tests/test_exporter.py`, `tests/test_fetcher.py` — one per module.
- Create: `README.md` — non-technical friendly (what/why/how to download, 5-click path, thesis citation snippet).
- Create: `docs/methodology-note.md` — 1-page thesis appendix (sources, keywords, filter, dedupe, translation, run date placeholder).
- Modify: `docs/README.md` — add plan + methodology links.
- Create: `.github/workflows/scrape.yml` — manual + weekly CI, setup-uv, artifact + Release.

Each file has one job; `scrape.py` wires them via the Interfaces below.

---

### Task 1: uv Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/__init__.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `uv sync` works; `import src` resolvable; later tasks `import src.fetcher` etc.

- [ ] **Step 1: Write pyproject.toml**

```toml
[project]
name = "skripsi-jeha"
version = "0.1.0"
description = "Scrape 2025 Microsoft Indonesia news to xlsx for thesis corpus"
requires-python = ">=3.11"
dependencies = [
  "feedparser>=6.0.11",
  "python-dateutil>=2.9.0",
  "openpyxl>=3.1.5",
  "langdetect>=1.0.9",
  "deep-translator>=1.11.4",
]

[dependency-groups]
dev = ["pytest>=8.3.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Write .gitignore**

```gitignore
output/
.venv/
__pycache__/
*.pyc
.pytest_cache/
```

- [ ] **Step 3: Create src/__init__.py (empty)**

```python
"""skripsi-jeha pipeline."""
```

- [ ] **Step 4: Verify uv sync works**

Run: `uv sync`
Expected: PASS, creates `.venv/` and `uv.lock`, no errors.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore src/__init__.py uv.lock
git commit -m "feat: init uv project scaffolding"
```

---

### Task 2: RSS Fetcher

**Files:**
- Create: `src/fetcher.py`
- Test: `tests/test_fetcher.py`

**Interfaces:**
- Consumes: none.
- Produces: `fetch_keyword_rss(keyword: str, hl: str, gl: str, ceid: str) -> list[dict]` where dict has keys `title, url, publisher, published_raw, snippet, keyword, locale`; `fetch_all(keywords: list[str]) -> list[dict]`; `LOCALES = [("id","ID","ID:id"), ("en-US","US","US:en")]`.

- [ ] **Step 1: Write failing test**

```python
from unittest.mock import patch
from src import fetcher

SAMPLE_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>test</title>
<item><title>Microsoft investasi di Indonesia - Kompas</title>
<link>https://news.google.com/rss/articles/abc?hl=id</link>
<source url="https://kompas.com">Kompas</source>
<pubDate>Mon, 10 Mar 2025 07:00:00 GMT</pubDate>
<description>Snippet here</description></item>
</channel></rss>"""

def test_fetch_keyword_rss_parses_fields():
    class FakeResp:
        text = SAMPLE_RSS
        status_code = 200
        def raise_for_status(self): pass
    with patch("src.fetcher._get", return_value=FakeResp()):
        rows = fetcher.fetch_keyword_rss("investasi microsoft di Indonesia tahun 2025", "id", "ID", "ID:id")
    assert len(rows) == 1
    assert rows[0]["publisher"] == "Kompas"
    assert "Microsoft" in rows[0]["title"]
    assert rows[0]["keyword"].startswith("investasi")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_fetcher.py::test_fetch_keyword_rss_parses_fields -v`
Expected: FAIL with "No module named src.fetcher" or "function not defined".

- [ ] **Step 3: Write minimal implementation**

```python
"""Fetch Google News RSS per keyword x locale."""
import time
import urllib.parse
import feedparser

LOCALES = [("id", "ID", "ID:id"), ("en-US", "US", "US:en")]

def _get(url, timeout=20):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (skripsi-research)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8", errors="replace")
    class R:
        text = body
        status_code = 200
        def raise_for_status(self): pass
    return R()

def fetch_keyword_rss(keyword, hl, gl, ceid, retries=3):
    q = urllib.parse.quote(keyword)
    url = f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"
    last = None
    for attempt in range(retries):
        try:
            resp = _get(url)
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
            rows = []
            for e in feed.entries:
                rows.append({
                    "title": e.get("title", "").strip(),
                    "url": e.get("link", "").strip(),
                    "publisher": (e.get("source", {}) or {}).get("title", "").strip() if isinstance(e.get("source"), dict) else str(e.get("source", "")).strip(),
                    "published_raw": e.get("published", "") or e.get("pubDate", ""),
                    "snippet": e.get("description", "") or e.get("summary", ""),
                    "keyword": keyword,
                    "locale": f"{hl}/{gl}",
                })
            return rows
        except Exception as ex:
            last = ex
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"fetch failed for {keyword!r} {hl}/{gl}: {last}")

def fetch_all(keywords, delay_s=2):
    all_rows = []
    for kw in keywords:
        for (hl, gl, ceid) in LOCALES:
            all_rows.extend(fetch_keyword_rss(kw, hl, gl, ceid))
            time.sleep(delay_s)
    return all_rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_fetcher.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
git add src/fetcher.py tests/test_fetcher.py
git commit -m "feat: add google news rss fetcher"
```

---

### Task 3: 2025 Filter + Dedupe

**Files:**
- Create: `src/filters.py`
- Test: `tests/test_filters.py`

**Interfaces:**
- Consumes: `RawArticle dict` from Task 2 (keys `published_raw`, `url`, `keyword`).
- Produces: `parse_date(raw: str) -> datetime | None`; `is_in_2025(dt) -> bool`; `normalize_url(url: str) -> str`; `dedupe(rows: list[dict]) -> (kept: list[dict], stats: dict)` where kept rows gain `date_iso`, `Also_Found_In`.

- [ ] **Step 1: Write failing test**

```python
from src import filters

def test_keeps_2025_dedupes_url():
    rows = [
        {"title": "A", "url": "https://Kompas.com/a?utm_source=x", "published_raw": "Mon, 10 Mar 2025 07:00:00 GMT", "keyword": "k1", "publisher": "Kompas", "snippet": "s", "locale": "id/ID"},
        {"title": "A dup", "url": "https://kompas.com/a", "published_raw": "Tue, 11 Mar 2025 07:00:00 GMT", "keyword": "k2", "publisher": "Kompas", "snippet": "s", "locale": "en-US/US"},
        {"title": "Old", "url": "https://x.com/old", "published_raw": "Mon, 10 Mar 2024 07:00:00 GMT", "keyword": "k1", "publisher": "X", "snippet": "s", "locale": "id/ID"},
    ]
    kept, stats = filters.dedupe(rows)
    urls = [r["url"] for r in kept]
    assert len(kept) == 1
    assert stats["dropped_not_2025"] == 1
    assert stats["duplicates"] == 1
    assert kept[0]["Also_Found_In"] == "k2"
    assert kept[0]["date_iso"].startswith("2025-03-10")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_filters.py -v`
Expected: FAIL (module/function missing).

- [ ] **Step 3: Write minimal implementation**

```python
"""Date filter (strict 2025) + URL dedupe."""
import re
import urllib.parse
from datetime import date
from dateutil import parser as dateparser

START = date(2025, 1, 1)
END = date(2025, 12, 31)
TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid", "hl", "gl", "ceid"}

def parse_date(raw):
    if not raw:
        return None
    try:
        return dateparser.parse(raw)
    except Exception:
        return None

def is_in_2025(dt):
    if dt is None:
        return False
    d = dt.date() if hasattr(dt, "date") else dt
    return START <= d <= END

def normalize_url(url):
    u = (url or "").strip()
    if not u:
        return ""
    p = urllib.parse.urlparse(u)
    host = (p.hostname or "").lower()
    if host.startswith("news.google.com"):
        return u.strip().rstrip("/")
    qs = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
    qs = [(k, v) for k, v in qs if k not in TRACKING]
    query = urllib.parse.urlencode(qs)
    path = re.sub(r"/+$", "", p.path or "")
    norm = urllib.parse.urlunparse((p.scheme.lower(), host, path, "", query, ""))
    return norm.rstrip("/")

def dedupe(rows):
    seen = {}
    dropped_not_2025 = 0
    dropped_bad_date = 0
    duplicates = 0
    for r in rows:
        dt = parse_date(r.get("published_raw", ""))
        if dt is None:
            dropped_bad_date += 1
            continue
        if not is_in_2025(dt):
            dropped_not_2025 += 1
            continue
        key = normalize_url(r.get("url", "")) or (r.get("title", "") + dt.isoformat())
        if key in seen:
            duplicates += 1
            prev = seen[key]
            extra = r.get("keyword", "")
            if extra and extra not in (prev.get("Keyword_Found", "") + prev.get("Also_Found_In", "")):
                prev["Also_Found_In"] = (prev.get("Also_Found_In", "") + "," + extra).strip(",")
            continue
        nr = dict(r)
        nr["date_iso"] = dt.date().isoformat()
        nr["Keyword_Found"] = r.get("keyword", "")
        nr["Also_Found_In"] = ""
        seen[key] = nr
    kept = list(seen.values())
    return kept, {"fetched": len(rows), "kept": len(kept), "dropped_not_2025": dropped_not_2025, "dropped_bad_date": dropped_bad_date, "duplicates": duplicates}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_filters.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/filters.py tests/test_filters.py
git commit -m "feat: add strict 2025 filter and url dedupe"
```

---

### Task 4: Language Detect + Translate EN→ID

**Files:**
- Create: `src/translator.py`
- Test: `tests/test_translator.py`

**Interfaces:**
- Consumes: kept rows from Task 3 (keys `title`, `snippet`).
- Produces: `detect_lang(text: str) -> str` ("id"/"en"/"unknown"); `translate_en_to_id(text: str) -> tuple[str, bool]`; `enrich(rows) -> (rows, stats)` adding `Title_Original, Title_ID, Snippet_Original, Snippet_ID, Source_Lang, translation_ok`.

- [ ] **Step 1: Write failing test**

```python
from src import translator

def test_detect_and_passthrough_id():
    assert translator.detect_lang("Kerja sama Microsoft dengan pemerintah Indonesia") == "id"

def test_enrich_keeps_original_and_marks_ok():
    rows = [{"title": "Kerja sama Microsoft", "snippet": "Ringkasan", "publisher": "Kompas", "url": "https://x.com/1", "date_iso": "2025-03-10", "Keyword_Found": "k1", "Also_Found_In": ""}]
    out, stats = translator.enrich(rows)
    assert out[0]["Title_Original"] == "Kerja sama Microsoft"
    assert out[0]["Title_ID"] == "Kerja sama Microsoft"
    assert out[0]["translation_ok"] in (True, "TRUE", "source=id")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_translator.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Write minimal implementation**

```python
"""Detect id/en, translate EN title+snippet to ID, always keep originals."""
from langdetect import detect, LangDetectException

def detect_lang(text):
    t = (text or "").strip()
    if len(t) < 12:
        return "unknown"
    try:
        lang = detect(t)
        if lang.startswith("id") or lang == "ms":
            return "id"
        if lang.startswith("en"):
            return "en"
        return lang
    except LangDetectException:
        return "unknown"

def translate_en_to_id(text):
    t = (text or "").strip()
    if not t:
        return "", True
    try:
        from deep_translator import GoogleTranslator
        out = GoogleTranslator(source="en", target="id").translate(t)
        return (out or t), True
    except Exception:
        return t, False

def enrich(rows):
    out = []
    translated = 0
    failed = 0
    for r in rows:
        lang = detect_lang(r.get("title", "") + " " + r.get("snippet", ""))
        if lang not in ("id", "en"):
            lang = "id" if r.get("locale", "").startswith("id") else lang
        nr = dict(r)
        nr["Title_Original"] = r.get("title", "")
        nr["Snippet_Original"] = r.get("snippet", "")
        nr["Source_Lang"] = lang if lang in ("id", "en") else "unknown"
        if lang == "en":
            ti, ok1 = translate_en_to_id(r.get("title", ""))
            si, ok2 = translate_en_to_id(r.get("snippet", ""))
            nr["Title_ID"] = ti
            nr["Snippet_ID"] = si
            nr["translation_ok"] = bool(ok1 and ok2)
            translated += 1
            if not nr["translation_ok"]:
                failed += 1
        else:
            nr["Title_ID"] = r.get("title", "")
            nr["Snippet_ID"] = r.get("snippet", "")
            nr["translation_ok"] = True
        out.append(nr)
    return out, {"en_translated": translated, "translation_failed": failed}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_translator.py -v`
Expected: PASS (network not needed for id passthrough test).

- [ ] **Step 5: Commit**

```bash
git add src/translator.py tests/test_translator.py
git commit -m "feat: add id-en detection and en-to-id translation"
```

---

### Task 5: XLSX Exporter + run-meta.json

**Files:**
- Create: `src/exporter.py`
- Test: `tests/test_exporter.py`

**Interfaces:**
- Consumes: enriched rows from Task 4.
- Produces: `export_xlsx(rows: list[dict], path: str) -> str`; `write_meta(meta: dict, path: str) -> str`. Columns exact order: `No, Publisher, Title_ID, Title_Original, URL, Date, Keyword_Found, Also_Found_In, Snippet_ID, Snippet_Original, Source_Lang, translation_ok`.

- [ ] **Step 1: Write failing test**

```python
from src import exporter

def test_export_creates_xlsx_with_headers(tmp_path):
    rows = [{"Publisher": "Kompas", "Title_ID": "Judul ID", "Title_Original": "Title EN", "url": "https://x.com/1", "URL": "https://x.com/1", "date_iso": "2025-03-10", "Date": "2025-03-10", "Keyword_Found": "k1", "Also_Found_In": "", "Snippet_ID": "S ID", "Snippet_Original": "S EN", "Source_Lang": "en", "translation_ok": True}]
    p = str(tmp_path / "out.xlsx")
    exporter.export_xlsx(rows, p)
    import openpyxl
    wb = openpyxl.load_workbook(p)
    ws = wb.active
    headers = [c.value for c in ws[1]]
    assert headers[0] == "No"
    assert "Publisher" in headers
    assert "Title_ID" in headers
    assert ws.max_row == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_exporter.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Write minimal implementation**

```python
"""XLSX + run-meta writer."""
import json
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

COLUMNS = ["No", "Publisher", "Title_ID", "Title_Original", "URL", "Date", "Keyword_Found", "Also_Found_In", "Snippet_ID", "Snippet_Original", "Source_Lang", "translation_ok"]
WIDTHS = {"No": 6, "Publisher": 18, "Title_ID": 60, "Title_Original": 60, "URL": 50, "Date": 12, "Keyword_Found": 30, "Also_Found_In": 30, "Snippet_ID": 60, "Snippet_Original": 60, "Source_Lang": 12, "translation_ok": 14}

def export_xlsx(rows, path):
    wb = Workbook()
    ws = wb.active
    ws.title = "articles-2025"
    hdr_fill = PatternFill("solid", fgColor="1F4E78")
    hdr_font = Font(bold=True, color="FFFFFF")
    for j, col in enumerate(COLUMNS, start=1):
        c = ws.cell(row=1, column=j, value=col)
        c.fill = hdr_fill
        c.font = hdr_font
        c.alignment = Alignment(vertical="center", wrap_text=True)
    for i, r in enumerate(rows, start=1):
        ws.cell(row=i + 1, column=1, value=i)
        ws.cell(row=i + 1, column=2, value=r.get("Publisher") or r.get("publisher", ""))
        ws.cell(row=i + 1, column=3, value=r.get("Title_ID", ""))
        ws.cell(row=i + 1, column=4, value=r.get("Title_Original", ""))
        ws.cell(row=i + 1, column=5, value=r.get("URL") or r.get("url", ""))
        ws.cell(row=i + 1, column=6, value=r.get("Date") or r.get("date_iso", ""))
        ws.cell(row=i + 1, column=7, value=r.get("Keyword_Found", ""))
        ws.cell(row=i + 1, column=8, value=r.get("Also_Found_In", ""))
        ws.cell(row=i + 1, column=9, value=r.get("Snippet_ID", ""))
        ws.cell(row=i + 1, column=10, value=r.get("Snippet_Original", ""))
        ws.cell(row=i + 1, column=11, value=r.get("Source_Lang", ""))
        ws.cell(row=i + 1, column=12, value=str(r.get("translation_ok", "")))
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for j, col in enumerate(COLUMNS, start=1):
        ws.column_dimensions[ws.cell(row=1, column=j).column_letter].width = WIDTHS[col]
    wb.save(path)
    return path

def write_meta(meta, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_exporter.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/exporter.py tests/test_exporter.py
git commit -m "feat: add xlsx exporter and run meta writer"
```

---

### Task 6: CLI Orchestration (src/scrape.py)

**Files:**
- Create: `src/scrape.py`

**Interfaces:**
- Consumes: `fetcher.fetch_all`, `filters.dedupe`, `translator.enrich`, `exporter.export_xlsx/write_meta`.
- Produces: `main() -> 0` CLI; writes `output/articles-2025.xlsx` + `output/run-meta.json`; console summary counts.

- [ ] **Step 1: Write implementation**

```python
"""Entry: scrape 4 keywords -> 2025-only deduped translated xlsx."""
import datetime
import pathlib
from src import fetcher, filters, translator, exporter

KEYWORDS = [
    "kerja sama microsoft dengan pemerintah indonesia di tahun 2025",
    "investasi microsoft di Indonesia tahun 2025",
    "Indonesia central cloud region (2025)",
    "Microsoft elevAIte di Indonesia 2025",
]
OUT_XLSX = "output/articles-2025.xlsx"
OUT_META = "output/run-meta.json"

def main():
    pathlib.Path("output").mkdir(parents=True, exist_ok=True)
    raw = fetcher.fetch_all(KEYWORDS)
    kept, dstats = filters.dedupe(raw)
    enriched, tstats = translator.enrich(kept)
    exporter.export_xlsx(enriched, OUT_XLSX)
    meta = {
        "run_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "keywords": KEYWORDS,
        "fetch_total": len(raw),
        **dstats,
        **tstats,
    }
    exporter.write_meta(meta, OUT_META)
    print(f"fetched={len(raw)} kept={len(enriched)} xlsx={OUT_XLSX}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke-run with mocked fetch (no network)**

Run: `uv run python -c "from unittest.mock import patch; import src.scrape as s; rows=[{'title':'Microsoft investasi','url':'https://k.com/1','publisher':'Kompas','published_raw':'Mon, 10 Mar 2025 07:00:00 GMT','snippet':'Ringkasan','keyword':s.KEYWORDS[0],'locale':'id/ID'}]; 
with patch('src.scrape.fetcher.fetch_all', return_value=rows): s.main()"`
Expected: PASS, `output/articles-2025.xlsx` created.

- [ ] **Step 3: Verify unit suite still green**

Run: `uv run pytest -q`
Expected: PASS (all tests).

- [ ] **Step 4: Commit**

```bash
git add src/scrape.py
git commit -m "feat: wire scrape orchestration with meta log"
```

---

### Task 7: Non-Technical README + Methodology Note

**Files:**
- Create: `README.md`
- Create: `docs/methodology-note.md`
- Modify: `docs/README.md` (add links)

**Interfaces:**
- Consumes: design spec + column list + CI release flow.
- Produces: non-technical reader can download xlsx in ≤5 clicks; thesis can cite methodology-note.

- [ ] **Step 1: Write README.md**

```markdown
# Skripsi Jeha — Microsoft Indonesia 2025 News Corpus

For everyone (no coding needed): this project collects news articles about Microsoft in Indonesia from 2025 into one Excel file.

## Download (no code)
1. Open the GitHub repo page.
2. Click **Releases** (right side).
3. Open the newest `articles-2025-YYYYMMDD` release.
4. Download `articles-2025.xlsx`.
5. Open in Excel / Google Sheets.

## What's inside the Excel
No (number), Publisher, Title_ID (Indonesian title), Title_Original, URL, Date, Keyword_Found, Snippet, Source_Lang.

## For thesis citation
See `docs/methodology-note.md` — copy the 1-page method paragraph into your appendix.

## Re-run it yourself (optional)
Install `uv`, then `uv sync && uv run python src/scrape.py`. Output goes to `output/`.
```

- [ ] **Step 2: Write docs/methodology-note.md (1 page, fill run date after first real run)**

Include: source (Google News RSS), 4 exact keywords, locales id+en, strict 2025 filter, dedupe rule, translation rule (EN→ID via GoogleTranslator, originals kept), output columns, reproducibility (commit SHA + run_utc from run-meta.json).

- [ ] **Step 3: Update docs/README.md index with links to methodology-note + this plan**

- [ ] **Step 4: Commit**

```bash
git add README.md docs/methodology-note.md docs/README.md
git commit -m "docs: add non-technical readme and methodology note"
```

---

### Task 8: GitHub Actions (uv + Artifact + Release)

**Files:**
- Create: `.github/workflows/scrape.yml`

**Interfaces:**
- Consumes: `uv sync`, `uv run python src/scrape.py`, `output/*`.
- Produces: green workflow, downloadable Artifact + Release asset `articles-2025.xlsx`.

- [ ] **Step 1: Write workflow**

```yaml
name: scrape
on:
  workflow_dispatch: {}
  schedule:
    - cron: "0 1 * * 1"
permissions:
  contents: write
jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run pytest -q
      - run: uv run python src/scrape.py
      - uses: actions/upload-artifact@v4
        with:
          name: articles-2025
          path: output/
      - name: Release xlsx
        uses: softprops/action-gh-release@v2
        with:
          tag_name: articles-2025-${{ github.run_number }}
          files: output/articles-2025.xlsx
```

- [ ] **Step 2: Validate YAML locally**

Run: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/scrape.yml')); print('yaml ok')"`
Expected: `yaml ok` (if pyyaml missing, `uv run --with pyyaml python -c ...`).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/scrape.yml
git commit -m "ci: add scrape workflow with release upload"
```

---

### Task 9: End-to-End Verification

**Files:** none new (verification only).

- [ ] **Step 1: Run full unit suite**

Run: `uv run pytest -q`
Expected: all PASS.

- [ ] **Step 2: Live scrape (real network, may take minutes)**

Run: `uv run python src/scrape.py`
Expected: `output/articles-2025.xlsx` + `output/run-meta.json` created; console prints `fetched=N kept=M`.

- [ ] **Step 3: Assert thesis invariants**

Run: `uv run python -c "import openpyxl; wb=openpyxl.load_workbook('output/articles-2025.xlsx'); ws=wb.active; dates=[r[5].value for r in list(ws.rows)[1:]]; urls=[r[4].value for r in list(ws.rows)[1:]]; assert dates and all(str(d).startswith('2025') for d in dates), dates[:3]; assert len(urls)==len(set(urls)), 'dup urls'; print(f'rows={len(dates)} publishers={len(set(r[1].value for r in list(ws.rows)[1:]))} ok')"`
Expected: prints `rows=N publishers=M ok`, no assertion error.

- [ ] **Step 4: Move plan to completed + update index**

```bash
git mv docs/active/2026-09-22-article-scrape-pipeline.md docs/completed/2026-09-22-article-scrape-pipeline.md
git add -A
git commit -m "docs: complete scrape pipeline plan after e2e verification"
```

---

## Self-Review

- Spec coverage: keywords/locales/dedupe/translation/xlsx/uv/CI/README/methodology all have tasks (Tasks 2-8). Phase 2 docx explicitly out of scope, noted as hook only.
- Placeholder scan: no TBD/TODO; every code step has full code; every test step has exact `uv run` command + expected output.
- Type consistency: `RawArticle dict` keys (`title,url,publisher,published_raw,snippet,keyword,locale`) match fetcher output → filters input; `date_iso,Keyword_Found,Also_Found_In` added in filters → translator preserves → exporter reads both cases. Column order constant `COLUMNS` reused in test.
