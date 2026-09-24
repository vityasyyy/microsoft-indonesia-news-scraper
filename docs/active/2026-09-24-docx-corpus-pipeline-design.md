# DOCX Corpus Pipeline (Phase 2) — Design Spec

Date: 2026-09-24
Status: Approved by user (CI-first revision)
Phase 1 prerequisite: done and proven (180-row xlsx, release `articles-2025-4`).

## 1. Goal & Context

Build a full-text corpus downloader that turns each row of `output/articles-2025.xlsx`
into one Indonesian-language `.docx` file for NVivo coding. One manual dispatch
produces one Release containing the xlsx **and** the docx zip, with versions matched.

Non-technical summary: the robot visits every article link, reads the full text,
translates English articles to Indonesian offline, and packs one Word file per
article into a zip your friend downloads next to the Excel file. Articles that
cannot be read (paywall, bot-block, removed) are listed honestly in `failed.csv`.

## 2. Requirements (agreed)

- Coverage: near-complete (Option B). Fetch chain with fallbacks; every URL ends
  `ok` or as a `failed.csv` row with reason. Thesis reports coverage honestly.
- Translation: full English bodies → Indonesian (offline Argos EN→ID, no API keys).
  Docx files contain Indonesian only; originals traceable via URL + Phase 1 xlsx.
- Execution: CI-first. Manual `workflow_dispatch` runs everything; local `make`
  targets are the dev/iteration path. No schedule, no push/PR triggers (unchanged).
- Speed: parallelized (thread pool, ~8 fetch workers). Target ~15–25 min per full CI run.
- Usage: `Makefile` (`corpus`, `corpus-test`, `corpus-zip`, `help`) so nobody memorizes
  long commands; README documents all of it.
- Keys/secrets: none. Extraction (`trafilatura` → `readability-lxml` fallback) and
  translation (Argos) are fully local/offline.
- Docs-sync (standing ask): README, repo description/topics, methodology note, and
  docs index must describe the ACTUAL workflow. Any behavior change updates docs in
  the same commit/PR. No drift.

## 3. Architecture

```
src/downloader.py    # fetch + extract one URL (chain + retries). No docx, no translate.
src/docx_builder.py  # assemble one docx from (title, meta, body_id). No network.
src/make_corpus.py   # KEYWORDS-free wiring: read xlsx -> pool -> write corpus/
                       # + failed.csv + corpus-meta.json (mirrors scrape.py pattern)
src/translator.py    # REUSED as-is (Argos EN->ID, cached model)
Makefile             # corpus, corpus-test (LIMIT=5), corpus-zip, help
corpus/              # gitignored build output (NNN_publisher_slug.docx)
.github/workflows/scrape.yml  # extended: ... scrape steps ... -> corpus steps ->
                       # upload output/ + corpus/ -> ONE Release:
                       # articles-2025.xlsx + corpus-articles-2025.zip
                       # (+ failed.csv and corpus-meta.json INSIDE the zip)
```

New deps (uv): `trafilatura`, `readability-lxml`, `python-docx`, `lxml`.
No new API keys. No new services.

## 4. Components

1. **downloader.fetch(url) -> FetchResult(ok, text, publisher_hint, reason, stage).**
   Chain: `requests` GET (10s timeout, research User-Agent, 2 tries, ~1s politeness)
   → `trafilatura` extract → if <300 chars, `readability-lxml` → if still thin,
   cleaned raw text → if HTTP 401/403 or paywall markers (`berlangganan`, `paywall`,
   `subscribe to read`), stop and return `reason=paywall|blocked|removed|thin`.
   Never raises; every URL resolves to ok/failed.
2. **docx_builder.build(path, title, meta, body_id).** `python-docx`: Title as
   Heading 1 → metadata lines (Publisher, Date, URL, Keyword_Found, Accessed UTC date)
   → body as Normal paragraphs (one per source paragraph, blank dropped). Indonesian only.
3. **make_corpus.main().** Read `output/articles-2025.xlsx` (must exist; if missing,
   run scrape first — CI guarantees order). ThreadPoolExecutor(8): fetch → detect lang
   (reuse translator) → translate EN bodies whole → build docx `NNN_<publisher>_<slug>.docx`
   (NNN = xlsx row number, zero-padded; slug from title ≤60 chars, ASCII, deduped).
   Write `corpus/failed.csv` (url, publisher, keyword, reason, stage) and
   `corpus-meta.json` (run_utc, xlsx_sha or release tag, counts: rows/ok/failed/by_reason).
   Exit 0 even with failures (failures are data, not errors); non-zero only on crash.
4. **Makefile.** `corpus` (full local: `uv run python -m src.make_corpus`), `corpus-test`
   (`LIMIT=5` env passthrough for fast iteration), `corpus-zip` (dated zip of corpus/
   + failed.csv + meta), `help`. All commands one line each.
5. **CI (scrape.yml extension).** After existing scrape steps: restore Argos model cache
   (`actions/cache`, key on model version) → `make corpus` → upload `output/` (as today)
   → zip corpus/ → single `action-gh-release` with BOTH files. Manual dispatch only.

## 5. Data Flow

```
dispatch -> pytest -> scrape.py -> articles-2025.xlsx (+ run-meta.json)
  -> make_corpus.py reads xlsx rows
    -> pool(8): fetch chain -> lang detect -> [EN? argos translate] -> build docx
  -> corpus/*.docx + failed.csv + corpus-meta.json
  -> Release: articles-2025.xlsx + corpus-articles-2025.zip
```

## 6. Error Handling

- Per-URL failures never abort the run; recorded with stage + reason.
- Translation failure → row goes to `failed.csv` (`reason=translate_failed`); no
  half-translated docx is written.
- Missing/corrupt xlsx input → clear error telling the operator to run scrape first.
- CI flakiness expectation (documented): datacenter IPs are bot-blocked more than home
  connections, so CI `failed.csv` may exceed a local run's. Same chain, same honesty.
- Argos model download failure in CI → job fails loudly (no silent English passthrough).

## 7. Docs-Sync Rule (binding)

README ("How it works" diagram, "When does scraping run?", "What's inside", corpus
section), repo description/topics, `docs/methodology-note.md` (add corpus + coverage
method), and `docs/README.md` index must match the implemented workflow. Every
behavior-changing commit updates the affected docs in the same commit. Verification
step of every future task: re-read the README section describing the changed behavior.

## 8. Testing / Verification (before hand-over)

- Unit tests per module, TDD (fetcher chain with mocked HTTP incl. paywall/thin paths;
  builder produces openable docx with Heading 1 + meta + paragraphs; orchestration with
  mocked fetch on 5 rows).
- `make corpus-test LIMIT=5` locally: 5 valid docx + failed.csv + meta.
- Full CI proof run asserting: every docx opens with non-empty title + body; bodies
  Indonesian (spot-check + langdetect sample); `failed.csv` reasons enumerated;
  `len(docx) + len(failed) == xlsx rows`; Release contains both files.
- Docs-sync check: README diagram + schedule + corpus sections re-read against implementation.

## 9. Non-Goals (YAGNI)

- No per-publisher custom scrapers (generic chain only; paywalled rows stay failed).
- No NVivo automation (deliverable is the import-ready folder/zip).
- No original-English full text in docx (Indonesian only per decision; URL preserves audit).
- No `corpus/` committed to git (gitignored; zip is the distribution unit).
- No schedule/push triggers (manual dispatch only, unchanged).

## 10. Known Limits

- Kompas.id paywalled rows will fail (`reason=paywall`) — legal and expected.
- Argos full-text translation quality varies on proper nouns; originals stay one click
  away via URL. Methodology note says so.
- Full CI run ~15–25 min; model cache trims repeat runs.

---
Spec self-review: no TBDs; chain/fallback/retry semantics explicit; file responsibilities
disjoint (fetch vs build vs wire); decisions Q1–Q4 each trace to a section; docs-sync
made binding per user ask; scope is one plan (corpus builder + CI extension + docs).
