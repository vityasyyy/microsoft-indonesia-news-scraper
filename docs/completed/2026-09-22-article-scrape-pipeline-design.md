# Article Scrape Pipeline — Design Spec (Phase 1: XLSX Inventory)

Date: 2026-09-22
Status: Approved by user
Option chosen: Option 2 — GitHub + Actions + Release artifacts (uv)

## 1. Goal & Context

Build an automated, reproducible pipeline that scrapes news articles about
Microsoft in Indonesia (2025) and produces an `xlsx` inventory for a friend's
thesis (skripsi). Phase 1 = inventory xlsx. Phase 2 (later) = folder of `docx`
full-text files for NVivo / Invivo coding.

Non-technical reader summary: this project searches Google News with 4 fixed
keywords, keeps only articles from year 2025, removes duplicates, translates
English titles/snippets to Indonesian, and saves everything into one Excel file
that can be downloaded from GitHub Releases. Every run is logged so the thesis
can describe exactly how the corpus was built.

## 2. Requirements (agreed)

- Keywords (exact, 4):
  1. `kerja sama microsoft dengan pemerintah indonesia di tahun 2025`
  2. `investasi microsoft di Indonesia tahun 2025`
  3. `Indonesia central cloud region (2025)`
  4. `Microsoft elevAIte di Indonesia 2025`
- Sources: Google News RSS first (broad). Architecture allows adding
  per-publisher scrapers later without changing output format.
- Languages: Indonesian + English. English rows translated to Indonesian.
- Date filter: strict `2025-01-01` to `2025-12-31` inclusive. No 2026 leakage.
- Volume: as many as possible per keyword, deduplicated by cleaned URL.
- XLSX must contain at minimum: number, publishers, titles. Extended (approved):
  `No | Publisher | Title_ID | Title_Original | URL | Date | Keyword_Found |
  Snippet_ID | Snippet_Original | Source_Lang | translation_ok`
  - `Title_ID` = final Indonesian title (translated if source was EN).
  - Originals always preserved for audit.
- Package manager: `uv` (fastest, per user request).
- Distribution: GitHub repo + README for non-technical readers + GitHub Actions
  CI that produces downloadable xlsx (Action artifact + Release asset).
- Docs: README + `docs/methodology-note.md` (1-page thesis appendix).

## 3. Architecture

```
pyproject.toml (uv, requires-python >=3.11)
uv.lock
src/scrape.py          # single entry point
output/                # gitignored; CI uploads from here
  articles-2025.xlsx
  run-meta.json
.github/workflows/scrape.yml  # manual + weekly schedule
README.md              # non-technical friendly
docs/methodology-note.md
docs/superpowers/specs/<this file>
```

No API keys. No database. Single script keeps review surface small and makes
thesis methodology easy to defend.

## 4. Components

1. **Searcher (`fetch_google_news_rss`)** — for each keyword × locale
   (`hl=id&gl=ID&ceid=ID:id` and `hl=en-US&gl=US&ceid=US:en`), GET
   `https://news.google.com/rss/search?q=<encoded>&hl=..&gl=..&ceid=..`.
   Parse RSS with `feedparser`. Extract title, link (follow redirect to resolve
   real publisher URL where possible), publisher (`source` field), pubDate,
   snippet/description. 2s delay between requests, 3x retry with backoff.
2. **Filter (`filter_2025 + dedupe`)** — parse dates with `dateutil`, keep only
   2025 range. Normalize URLs (strip tracking params, lowercase host, strip
   trailing slash) and dedupe, keeping first-seen keyword in `Keyword_Found`
   plus `Also_Found_In` for transparency.
3. **Language + Translate** — detect with `langdetect` on title. If `en`,
   translate title + snippet via `deep-translator` (Google, free, no key).
   On failure: keep original, set `translation_ok=FALSE`, log error. `id`
   rows pass through with `translation_ok=TRUE (source=id)`.
4. **Exporter** — `openpyxl`: styled header, frozen pane, autofilter,
   column widths, date format `YYYY-MM-DD`. Also writes `run-meta.json`
   (run timestamp UTC, keyword counts, fetched/kept/dropped/duplicates,
   translation failures).
5. **CI (`scrape.yml`)** — `actions/setup-python` + `astral-sh/setup-uv`,
   `uv sync`, `uv run python src/scrape.py`, upload `output/*` as artifact,
   create dated Release (`articles-2025-YYYYMMDD-HHMM`) with xlsx attached.
   Triggers: `workflow_dispatch` (manual button) + weekly cron.

## 5. Data Flow

```
keywords (4) × locales (2) → RSS fetch → raw rows
  → date-parse → 2025 filter → URL-normalize → dedupe
  → lang-detect → translate EN→ID → xlsx + run-meta.json
  → CI artifact + Release
```

Phase 2 hook: `URL` column is the join key for the future full-text
downloader (`src/download_docx.py`) — no re-scrape needed.

## 6. Error Handling

- HTTP / rate-limit: 2s delay, 3 retries, exponential backoff; per-keyword
  failure does not abort whole run (logs + continues).
- Date-parse failure: drop row, count in `run-meta.json`.
- Translation failure: keep original text, `translation_ok=FALSE`.
- Empty result for a keyword: not an error; logged, xlsx still produced.
- CI failure: workflow fails loudly, no Release created.

## 7. Testing / Verification (before hand-over)

- Local `uv sync && uv run python src/scrape.py` produces xlsx.
- Assert: all `Date` in 2025, no duplicate `URL`, all `Source_Lang=en` rows
  have `Title_ID` filled (or `translation_ok=FALSE` with reason logged).
- CI: workflow green on `main`, artifact + Release downloadable.
- README readability check: a non-technical reader can go from landing page
  to downloaded xlsx in ≤5 clicks.

## 8. Non-Goals (YAGNI)

- No per-publisher HTML scrapers in Phase 1.
- No SQLite / DB layer.
- No full-text extraction or docx generation (Phase 2).
- No row cap for now (user chose unlimited; revisit if >1000 rows breaks NVivo workflow).
- No paid APIs (NewsAPI, SerpAPI).

## 9. Open Follow-ups (Phase 2 preview)

- `src/download_docx.py`: fetch each URL full text (trafilatura/newspaper4k),
  save `corpus/001_<publisher>_<slug>.docx` with title, metadata header,
  source link, accessed date. Translate full text EN→ID.
- Thesis sampling note: if corpus >300, recommend purposive sampling criteria.

---
Spec self-review: no TBDs; architecture matches features; scope is single plan;
`Title_ID` vs `Title_Original` semantics made explicit; unlimited volume risk
noted with revisit trigger.
