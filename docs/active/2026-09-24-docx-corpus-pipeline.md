# DOCX Corpus Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first, parallel full-text corpus builder that turns every xlsx row into one Indonesian `.docx` file, plus a CI extension that ships the corpus zip in the same Release as the xlsx.

**Architecture:** Three focused modules (`downloader` fetches+extracts, `docx_builder` assembles, `make_corpus` wires a thread pool over xlsx rows) reusing `src/translator.py` as-is; `Makefile` for local runs; `scrape.yml` gains corpus steps and a two-file Release.

**Tech Stack:** Python >=3.11, uv, requests, trafilatura, readability-lxml, lxml, python-docx, openpyxl (already present), argostranslate via src/translator (already present), pytest

## Global Constraints

- Input: `output/articles-2025.xlsx` (must exist; error clearly if missing).
- Filenames exact: `NNN_<publisher-slug>_<title-slug>.docx`, NNN = xlsx row number zero-padded to 3.
- Slugs exact: lowercase, `[^a-z0-9]+` → `-`, strip `-`, truncate 60 chars, fallback `article` / publisher fallback `unknown`.
- Extraction bar: body text must be >= `MIN_CHARS = 300` characters after cleaning, else next fallback.
- Fetch chain exact order: `requests` (timeout 10s, 2 tries) → `trafilatura` → `readability-lxml` → cleaned raw text → fail.
- Failure reasons closed set: `paywall`, `blocked`, `removed`, `thin`, `fetch_error`, `translate_failed`.
- Paywall markers (case-insensitive substring): `berlangganan`, `paywall`, `subscribe to read`, `lanjutkan membaca`, `akses penuh`.
- Docx files contain Indonesian only; translation failure → `failed.csv`, never half-translated files.
- Exit code 0 even with per-URL failures; non-zero only on crash/missing input.
- Pool size exact: `MAX_WORKERS = 8`; politeness `DELAY_S = 1.0` per request attempt.
- `LIMIT` env var: `0`/unset = all rows, `>0` = first N rows (for `make corpus-test`).
- `corpus/` is gitignored; zip name exact: `corpus-articles-2025.zip`.
- No API keys. Manual CI dispatch only (no schedule/push triggers — unchanged).
- Docs-sync binding: README + methodology note + docs index updated in the same change as behavior.

---

## File Structure

- Modify: `pyproject.toml` — add `trafilatura`, `readability-lxml`, `python-docx`, `lxml`. Owns deps only.
- Modify: `.gitignore` — add `corpus/` and `corpus-*.zip`. Owns ignore rules only.
- Create: `Makefile` — `corpus`, `corpus-test`, `corpus-zip`, `help`. Owns runnable shortcuts only.
- Create: `src/downloader.py` — `fetch(url) -> dict` with keys `ok, text, reason, stage`. Owns network + extraction, never translates or writes files.
- Create: `src/docx_builder.py` — `build(path, title, meta, body_id) -> str`. Owns docx assembly, never network.
- Create: `src/make_corpus.py` — `read_rows(xlsx)`, `slugify(text, fallback)`, `process_row(row)`, `main()`. Owns wiring + pool, no extraction logic, no docx internals.
- Create: `tests/test_downloader.py`, `tests/test_docx_builder.py`, `tests/test_make_corpus.py` — one per module.
- Modify: `.github/workflows/scrape.yml` — append corpus steps + model cache + two-file Release.
- Modify: `README.md` — add "Phase 2: docx corpus" section (usage + diagram delta + coverage honesty).
- Modify: `docs/methodology-note.md` — add "Corpus (docx) method" subsection.
- Modify: `docs/README.md` — link the Phase 2 spec + note corpus deliverable.

---

### Task 1: Deps + Makefile + Ignores

**Files:**
- Modify: `pyproject.toml`
- Modify: `.gitignore`
- Create: `Makefile`

**Interfaces:**
- Consumes: nothing.
- Produces: `uv sync` installs new deps; `make help` lists targets; `corpus/` ignored.

- [ ] **Step 1: Add dependencies to pyproject.toml**

```toml
  "trafilatura>=2.0.0",
  "readability-lxml>=0.8.1",
  "python-docx>=1.1.2",
  "lxml>=5.0.0",
```

Append these four lines inside the existing `dependencies = [` list (after `"lxml"` is NOT present — add all four; `lxml` is required by readability).

- [ ] **Step 2: Append ignores to .gitignore**

```gitignore
corpus/
corpus-*.zip
```

- [ ] **Step 3: Write Makefile**

```make
.PHONY: corpus corpus-test corpus-zip help

corpus: ## Full local corpus build (reads output/articles-2025.xlsx)
	uv run python -m src.make_corpus

corpus-test: ## Fast iteration on first N rows (default 5): make corpus-test LIMIT=10
	uv run python -m src.make_corpus

corpus-zip: ## Zip corpus/ + failed.csv + meta for sending
	./scripts/zip_corpus.sh

help: ## List targets
	@grep -E '^[a-z-]+: ## ' Makefile
```

- [ ] **Step 4: Verify sync + help**

Run: `uv sync`
Expected: PASS, resolves new packages.

Run: `make help`
Expected: lists `corpus`, `corpus-test`, `corpus-zip`, `help`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock .gitignore Makefile
git commit -m "feat(corpus): add deps, makefile and ignores"
```

---

### Task 2: Downloader (fetch chain)

**Files:**
- Create: `src/downloader.py`
- Test: `tests/test_downloader.py`

**Interfaces:**
- Consumes: raw URL string.
- Produces: `fetch(url: str) -> dict` with keys `ok: bool`, `text: str` (cleaned, `""` on failure), `reason: str` (`""` on ok, else one of the closed set), `stage: str` (`trafilatura`/`readability`/`raw`/`fetch`/`paywall-check`). Constants `MIN_CHARS = 300`, `MAX_WORKERS = 8`, `DELAY_S = 1.0`, `TIMEOUT_S = 10`, `PAYWALL_MARKERS = ("berlangganan", "paywall", "subscribe to read", "lanjutkan membaca", "akses penuh")`, `USER_AGENT = "Mozilla/5.0 (news-corpus-research)"`.

- [ ] **Step 1: Write the failing test**

```python
from unittest.mock import patch
from src import downloader

HTML = "<html><body><article><p>" + "Berita tentang Microsoft di Indonesia. " * 30 + "</p></article></body></html>"

def test_fetch_ok_via_trafilatura():
    class R:
        status_code = 200
        text = HTML
        def raise_for_status(self): pass
    with patch("src.downloader._get", return_value=R()):
        with patch("time.sleep", return_value=None):
            res = downloader.fetch("https://example.com/a")
    assert res["ok"] is True
    assert len(res["text"]) >= 300
    assert res["reason"] == ""

def test_fetch_paywall_marked_not_raised():
    class R:
        status_code = 200
        text = "<html><body>Silakan berlangganan untuk lanjutkan membaca</body></html>"
        def raise_for_status(self): pass
    with patch("src.downloader._get", return_value=R()):
        with patch("time.sleep", return_value=None):
            res = downloader.fetch("https://example.com/pay")
    assert res["ok"] is False
    assert res["reason"] == "paywall"

def test_fetch_404_marked_removed():
    import requests
    with patch("src.downloader._get", side_effect=requests.HTTPError("404")):
        with patch("time.sleep", return_value=None):
            res = downloader.fetch("https://example.com/gone")
    assert res["ok"] is False
    assert res["reason"] in ("removed", "fetch_error")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_downloader.py -v`
Expected: FAIL with "No module named src.downloader" or missing `fetch`/`_get`.

- [ ] **Step 3: Write minimal implementation**

```python
"""Fetch one article URL and extract body text via fallback chain."""
import re
import time
import requests
import trafilatura

MIN_CHARS = 300
MAX_WORKERS = 8
DELAY_S = 1.0
TIMEOUT_S = 10
USER_AGENT = "Mozilla/5.0 (news-corpus-research)"
PAYWALL_MARKERS = ("berlangganan", "paywall", "subscribe to read", "lanjutkan membaca", "akses penuh")
TAG_RE = re.compile(r"<[^>]+>")

def _get(url, timeout=TIMEOUT_S):
    return requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)

def _clean(text):
    t = TAG_RE.sub(" ", text or "")
    return re.sub(r"\s+", " ", t).strip()

def _paywalled(html):
    low = (html or "").lower()
    return any(m in low for m in PAYWALL_MARKERS)

def fetch(url):
    html = ""
    for _ in range(2):
        try:
            time.sleep(DELAY_S)
            r = _get(url)
            if r.status_code in (401, 403):
                return {"ok": False, "text": "", "reason": "blocked", "stage": "fetch"}
            if r.status_code == 404:
                return {"ok": False, "text": "", "reason": "removed", "stage": "fetch"}
            r.raise_for_status()
            html = r.text or ""
            break
        except Exception:
            html = ""
    if not html:
        return {"ok": False, "text": "", "reason": "fetch_error", "stage": "fetch"}
    if _paywalled(html):
        return {"ok": False, "text": "", "reason": "paywall", "stage": "paywall-check"}
    text = (trafilatura.extract(html) or "").strip()
    if len(text) >= MIN_CHARS:
        return {"ok": True, "text": text, "reason": "", "stage": "trafilatura"}
    try:
        from readability import Document
        text2 = _clean(Document(html).summary())
        if len(text2) >= MIN_CHARS:
            return {"ok": True, "text": text2, "reason": "", "stage": "readability"}
    except Exception:
        text2 = ""
    raw = _clean(html)
    if len(raw) >= MIN_CHARS:
        return {"ok": True, "text": raw, "reason": "", "stage": "raw"}
    return {"ok": False, "text": "", "reason": "thin", "stage": "raw"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_downloader.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/downloader.py tests/test_downloader.py
git commit -m "feat(corpus): add fetch chain with fallbacks"
```

---

### Task 3: Docx Builder

**Files:**
- Create: `src/docx_builder.py`
- Test: `tests/test_docx_builder.py`

**Interfaces:**
- Consumes: `path: str`, `title: str`, `meta: dict` with keys `Publisher, Date, URL, Keyword_Found, Accessed`, `body_id: str` (non-empty Indonesian text).
- Produces: `build(path: str, title: str, meta: dict, body_id: str) -> str` (returns path; raises ValueError on empty body).

- [ ] **Step 1: Write the failing test**

```python
from docx import Document
from src import docx_builder

def test_build_heading_meta_paragraphs(tmp_path):
    p = str(tmp_path / "001_test.docx")
    meta = {"Publisher": "Kompas.com", "Date": "2025-03-10", "URL": "https://x.com/1", "Keyword_Found": "k1", "Accessed": "2026-09-24"}
    body = "Paragraf satu tentang Microsoft.\n\nParagraf dua tentang Indonesia."
    docx_builder.build(p, "Judul Artikel", meta, body)
    doc = Document(p)
    assert doc.paragraphs[0].style.name.startswith("Heading 1")
    assert "Judul Artikel" in doc.paragraphs[0].text
    texts = [x.text for x in doc.paragraphs]
    assert any("Kompas.com" in t and "2025-03-10" in t for t in texts)
    assert any("Paragraf satu" in t for t in texts)
    assert any("Paragraf dua" in t for t in texts)

def test_build_rejects_empty_body(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        docx_builder.build(str(tmp_path / "x.docx"), "T", {}, "   ")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_docx_builder.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Write minimal implementation**

```python
"""Assemble one Indonesian docx: Heading-1 title, metadata, body paragraphs."""
from docx import Document

def build(path, title, meta, body_id):
    body = (body_id or "").strip()
    if not body:
        raise ValueError("empty Indonesian body")
    doc = Document()
    doc.add_heading((title or "Tanpa judul").strip(), level=1)
    doc.add_paragraph(
        f"Publisher: {meta.get('Publisher', '')} | "
        f"Date: {meta.get('Date', '')} | "
        f"Keyword: {meta.get('Keyword_Found', '')} | "
        f"Accessed: {meta.get('Accessed', '')}"
    )
    doc.add_paragraph(f"URL: {meta.get('URL', '')}")
    for para in body.split("\n"):
        para = para.strip()
        if para:
            doc.add_paragraph(para)
    doc.save(path)
    return path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_docx_builder.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/docx_builder.py tests/test_docx_builder.py
git commit -m "feat(corpus): add docx builder"
```

---

### Task 4: Orchestration (make_corpus)

**Files:**
- Create: `src/make_corpus.py`
- Test: `tests/test_make_corpus.py`

**Interfaces:**
- Consumes: `downloader.fetch(url)`, `translator.detect_lang(text)`, `translator.translate_en_to_id(text)`, `docx_builder.build(...)`, xlsx at `XLSX_IN = "output/articles-2025.xlsx"` with columns `No, Publisher, Title_ID, Title_Original, URL, Date, Keyword_Found`.
- Produces: `slugify(text: str, fallback: str) -> str`; `read_rows(xlsx: str) -> list[dict]` (keys `No, Publisher, Title, URL, Date, Keyword_Found`); `process_row(row: dict, outdir: str) -> dict` (keys `status` in `ok/failed`, plus `file/reason/stage`); `main() -> int` (0 ok, 1 crash/missing input). Writes `corpus/NNN_slug.docx`, `corpus/failed.csv`, `corpus/corpus-meta.json`.

- [ ] **Step 1: Write the failing test**

```python
import csv
from unittest.mock import patch
from src import make_corpus

def test_slugify_rules():
    assert make_corpus.slugify("Kompas.com", "unknown") == "kompas-com"
    assert make_corpus.slugify("  ", "unknown") == "unknown"
    assert len(make_corpus.slugify("x" * 100, "a")) == 60

def test_process_row_ok_path_translates_en(tmp_path):
    row = {"No": 7, "Publisher": "DCD", "Title": "Cloud region launched in Indonesia", "URL": "https://x.com/7", "Date": "2025-06-01", "Keyword_Found": "k3"}
    with patch("src.make_corpus.downloader.fetch", return_value={"ok": True, "text": "Microsoft launched its first cloud region in Indonesia", "reason": "", "stage": "trafilatura"}):
        with patch("src.make_corpus.translator.detect_lang", return_value="en"):
            with patch("src.make_corpus.translator.translate_en_to_id", return_value=("TERJEMAHAN", True)):
                res = make_corpus.process_row(row, str(tmp_path))
    assert res["status"] == "ok"
    assert res["file"].startswith("007_")
    assert res["file"].endswith(".docx")

def test_process_row_failed_fetch_logged(tmp_path):
    row = {"No": 8, "Publisher": "K", "Title": "T", "URL": "https://x.com/8", "Date": "2025-06-01", "Keyword_Found": "k1"}
    with patch("src.make_corpus.downloader.fetch", return_value={"ok": False, "text": "", "reason": "paywall", "stage": "paywall-check"}):
        res = make_corpus.process_row(row, str(tmp_path))
    assert res["status"] == "failed"
    assert res["reason"] == "paywall"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_make_corpus.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Write minimal implementation**

```python
"""Wire xlsx rows -> pooled fetch/translate/build -> corpus/ + failed.csv + meta."""
import csv
import datetime
import json
import os
import pathlib
import re
from concurrent.futures import ThreadPoolExecutor

import openpyxl

from src import downloader, docx_builder, translator

XLSX_IN = "output/articles-2025.xlsx"
OUT_DIR = "corpus"
LIMIT = int(os.environ.get("LIMIT", "0") or 0)

def slugify(text, fallback):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:60].strip("-")
    return s or fallback

def read_rows(xlsx):
    wb = openpyxl.load_workbook(xlsx)
    ws = wb.active
    headers = [c.value for c in ws[1]]
    idx = {h: headers.index(h) for h in ("No", "Publisher", "Title_ID", "Title_Original", "URL", "Date", "Keyword_Found")}
    rows = []
    for r in list(ws.rows)[1:]:
        v = [c.value for c in r]
        rows.append({
            "No": v[idx["No"]],
            "Publisher": v[idx["Publisher"]] or "",
            "Title": (v[idx["Title_ID"]] or v[idx["Title_Original"]] or "").strip(),
            "URL": (v[idx["URL"]] or "").strip(),
            "Date": str(v[idx["Date"]] or ""),
            "Keyword_Found": v[idx["Keyword_Found"]] or "",
        })
    return [r for r in rows if r["URL"]]

def process_row(row, outdir):
    n = int(row["No"])
    pub = slugify(row["Publisher"], "unknown")
    got = downloader.fetch(row["URL"])
    if not got["ok"]:
        return {"status": "failed", "No": n, "URL": row["URL"], "Publisher": row["Publisher"], "Keyword_Found": row["Keyword_Found"], "reason": got["reason"], "stage": got["stage"]}
    lang = translator.detect_lang((row["Title"] or "") + " " + (got["text"] or ""))
    if lang == "en":
        body, ok = translator.translate_en_to_id(got["text"])
        if not ok:
            return {"status": "failed", "No": n, "URL": row["URL"], "Publisher": row["Publisher"], "Keyword_Found": row["Keyword_Found"], "reason": "translate_failed", "stage": "translate"}
    else:
        body = got["text"]
    title = row["Title"] or "Tanpa judul"
    fname = f"{n:03d}_{pub}_{slugify(title, 'article')}.docx"
    meta = {"Publisher": row["Publisher"], "Date": row["Date"], "URL": row["URL"], "Keyword_Found": row["Keyword_Found"], "Accessed": datetime.date.today().isoformat()}
    docx_builder.build(str(pathlib.Path(outdir) / fname), title, meta, body)
    return {"status": "ok", "No": n, "file": fname}

def main():
    if not pathlib.Path(XLSX_IN).exists():
        print(f"missing {XLSX_IN}: run `make` scrape first (`uv run python -m src.scrape`)")
        return 1
    outdir = pathlib.Path(OUT_DIR)
    outdir.mkdir(parents=True, exist_ok=True)
    rows = read_rows(XLSX_IN)
    if LIMIT > 0:
        rows = rows[:LIMIT]
    results = []
    with ThreadPoolExecutor(max_workers=downloader.MAX_WORKERS) as pool:
        for res in pool.map(lambda r: process_row(r, str(outdir)), rows):
            results.append(res)
    ok = [r for r in results if r["status"] == "ok"]
    failed = [r for r in results if r["status"] != "ok"]
    with open(outdir / "failed.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["No", "URL", "Publisher", "Keyword_Found", "reason", "stage"])
        w.writeheader()
        w.writerows([{"No": r["No"], "URL": r["URL"], "Publisher": r["Publisher"], "Keyword_Found": r["Keyword_Found"], "reason": r["reason"], "stage": r["stage"]} for r in failed])
    by_reason = {}
    for r in failed:
        by_reason[r["reason"]] = by_reason.get(r["reason"], 0) + 1
    with open(outdir / "corpus-meta.json", "w", encoding="utf-8") as f:
        json.dump({"run_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "xlsx": XLSX_IN, "rows": len(rows), "ok": len(ok), "failed": len(failed), "by_reason": by_reason}, f, ensure_ascii=False, indent=2)
    print(f"rows={len(rows)} ok={len(ok)} failed={len(failed)} dir={OUT_DIR}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_make_corpus.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/make_corpus.py tests/test_make_corpus.py
git commit -m "feat(corpus): add pooled orchestration"
```

---

### Task 5: CI Extension + Docs-Sync

**Files:**
- Modify: `.github/workflows/scrape.yml`
- Create: `scripts/zip_corpus.sh`
- Modify: `README.md` (add corpus section + diagram delta)
- Modify: `docs/methodology-note.md` (add corpus method subsection)
- Modify: `docs/README.md` (link Phase 2 spec)

**Interfaces:**
- Consumes: `corpus/` from Task 4, existing Release step.
- Produces: one dispatch → Release with `articles-2025.xlsx` + `corpus-articles-2025.zip`; docs describe reality.

- [ ] **Step 1: Create scripts/zip_corpus.sh**

```bash
#!/usr/bin/env bash
set -euo pipefail
test -d corpus || { echo "missing corpus/: run \`make corpus\` first"; exit 1; }
zip -qr "corpus-articles-2025.zip" corpus
echo "wrote corpus-articles-2025.zip"
```

Run: `chmod +x scripts/zip_corpus.sh`

- [ ] **Step 2: Extend the workflow (append after the scrape run step, before upload)**

Replace the upload + release block with:

```yaml
      - run: uv run python -m src.scrape
      - name: Restore Argos model cache
        uses: actions/cache@v4
        with:
          path: ~/.local/share/argos-translate
          key: argos-model-en-id-1.9
      - run: make corpus
      - run: ./scripts/zip_corpus.sh
      - uses: actions/upload-artifact@v4
        with:
          name: articles-2025
          path: output/
      - uses: actions/upload-artifact@v4
        with:
          name: corpus-2025
          path: corpus/
      - name: Release xlsx + corpus
        uses: softprops/action-gh-release@v2
        with:
          tag_name: articles-2025-${{ github.run_number }}
          files: |
            output/articles-2025.xlsx
            corpus-articles-2025.zip
```

Keep the WHEN-THIS-RUNS comment accurate (manual only — unchanged).

- [ ] **Step 3: Validate YAML**

Run: `python3 -c "import yaml; d=yaml.safe_load(open('.github/workflows/scrape.yml')); print(sorted(d.get('on', d.get(True, {})).keys() if isinstance(d.get('on', {}), dict) else d.get('on')))"`
Expected: prints `['workflow_dispatch']` (no schedule).

- [ ] **Step 4: README — append corpus section after "What's inside the Excel"**

```markdown
## Phase 2: docx corpus (for NVivo)

- Build locally: `make corpus` (reads `output/articles-2025.xlsx`, writes `corpus/NNN_publisher_slug.docx` + `failed.csv` + `corpus-meta.json`). Fast check: `make corpus-test LIMIT=5`. Zip for sending: `make corpus-zip`.
- Via CI: Actions → `scrape` → `Run workflow` attaches `corpus-articles-2025.zip` to the same Release as the xlsx.
- Coverage is honest: paywalled/bot-blocked/removed links land in `failed.csv` with reasons — report the ok-rate in your thesis.
```

Also extend the mermaid diagram: after `E["articles-2025.xlsx..."]` add `E --> C["corpus/*.docx\nIndonesian full text"]` and `C --> R`. Keep all existing nodes.

- [ ] **Step 5: Methodology note — append subsection**

```markdown
## Corpus (docx) method
Each xlsx row was fetched (requests → trafilatura → readability fallback), language-detected on cleaned text, English bodies translated offline (Argos EN→ID), and saved as `NNN_publisher_slug.docx` (Heading-1 title, metadata block, full Indonesian body). Unfetchable URLs (paywall, bot-block, removed, thin) are listed in `failed.csv` with reasons; report the ok-rate alongside the corpus. Reproduce: `make corpus` on the cited xlsx, or re-dispatch the pinned release workflow.
```

- [ ] **Step 6: Docs index — add Phase 2 spec link under Current docs**

```markdown
- [DOCX Corpus Pipeline — Design Spec (active)](active/2026-09-24-docx-corpus-pipeline-design.md) — full-text Indonesian docx corpus for NVivo (moves to completed/ when built).
```

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/scrape.yml scripts/zip_corpus.sh README.md docs/methodology-note.md docs/README.md
git commit -m "feat(corpus): attach corpus zip to release and sync docs"
```

---

### Task 6: E2E Verification (lead-owned acceptance)

**Files:** none new (verification only; move plan + spec to completed/ after).

- [ ] **Step 1: Full unit suite green**

Run: `uv run pytest -q`
Expected: all PASS (16 total: 8 existing + 8 new).

- [ ] **Step 2: Local fast corpus**

Run: `LIMIT=5 make corpus-test` (note: Makefile `corpus-test` target runs `make_corpus` which reads `LIMIT` env)
Expected: `corpus/` holds 5 docx (or fewer + `failed.csv` rows), `corpus-meta.json` sums reconcile.

- [ ] **Step 3: CI proof run + Release asserts**

Dispatch workflow, watch to green, download both assets, assert: every docx opens with non-empty title + body; `failed.csv` reasons within closed set; `len(docx) + len(failed) == xlsx rows`.

- [ ] **Step 4: Move plan + spec to completed/ + update index**

```bash
git mv docs/active/2026-09-24-docx-corpus-pipeline-design.md docs/completed/
git mv docs/active/2026-09-24-docx-corpus-pipeline.md docs/completed/
git add -A
git commit -m "docs: complete docx corpus pipeline"
```

---

## Self-Review

- Spec coverage: near-complete chain (Task 2) ✓; full-body offline translation (Tasks 3–4, Argos reuse) ✓; parallel pool (Task 4, MAX_WORKERS=8) ✓; Makefile + docs usage (Tasks 1, 5) ✓; no API keys (no new services anywhere) ✓; Indonesian-only docx (Task 3, failure→failed.csv) ✓; CI-first single Release (Task 5) ✓; docs-sync binding (Task 5 steps 4–6 + Task 6 verification re-read) ✓.
- Placeholder scan: no TBD/TODO; every code step has full code; YAML/README/methodology blocks verbatim.
- Type consistency: `FetchResult` keys (`ok/text/reason/stage`) match `process_row` reads; `meta` keys (`Publisher/Date/URL/Keyword_Found/Accessed`) match builder use; `failed.csv` columns match writer; `corpus-meta.json` keys match spec §4; slug rules match Global Constraints; `LIMIT`/`MAX_WORKERS`/`MIN_CHARS` values match spec.
