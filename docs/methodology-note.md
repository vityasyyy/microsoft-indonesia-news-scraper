# Methodology Note — Microsoft Indonesia 2025 News Corpus

## Source
Articles were collected from Google News RSS search (`news.google.com/rss/search`), no API keys required. Queries ran in two locales: Indonesian (`hl=id, gl=ID, ceid=ID:id`) and English (`hl=en-US, gl=US, ceid=US:en`).

## Queries (15)
Baseline group:
1. `kerja sama microsoft dengan pemerintah indonesia di tahun 2025`
2. `investasi microsoft di Indonesia tahun 2025`
3. `Indonesia central cloud region microsoft (2025)`
4. `Microsoft elevAIte di Indonesia 2025`

Government group (Microsoft-related only):
`microsoft kementerian` · `microsoft komdigi` · `microsoft kementerian komunikasi dan digital` · `microsoft kemenag` · `microsoft kementerian investasi` · `microsoft kemenko perekonomian` · `microsoft kementerian keuangan` · `microsoft kementerian pendidikan` · `microsoft pemerintah daerah` · `microsoft pemprov` · `microsoft dinas pendidikan`

Each query ran with `after:`/`before:` for six two-month windows covering 2025 (`2025-01-01`–`2025-03-01`, `2025-03-01`–`2025-05-01`, …, `2025-11-01`–`2026-01-01`) in both locales. `run-meta.json` records raw/kept/dropped counts per query, window, and locale, plus any query errors.

## Date filter (strict 2025)
Only articles dated `2025-01-01` to `2025-12-31` inclusive were kept. Items with unparseable or out-of-range dates were dropped and counted; no 2026 leakage.

## Microsoft relevance gate
Only rows whose HTML-cleaned title or snippet contained a Microsoft signal were kept: `microsoft`, `azure`, `microsoft 365`, `office 365`, `copilot`, `linkedin`, `github`, `elevaiate`, `elevate`. Dropped rows were counted per query/window and sampled by title in `run-meta.json`. The gate applies to both baseline and government queries.

## Dedupe rule
Google News links were keyed with all query parameters removed. Other URLs had tracking parameters stripped and the remaining parameters sorted. The first-seen article was kept; repeats found under other queries were recorded in `Also_Found_In`, and every group that found the article was recorded in `Found_In_Groups`.

## Language rule
Language was detected on HTML-cleaned title+snippet text and labeled `id`, `en`, `other`, or `unknown`. Detection is seeded for reproducibility. The original title and snippet are stored exactly as published — English stays English, Indonesian stays Indonesian. There is no machine translation. An `unknown` detection is never coerced to `id`.

## Classification
`Source_Type` is `government` when the publisher host from the RSS `<source url=...>` link ends with `.go.id`, otherwise `other`. `Government_Body` records the first matched ministry/agency alias from the title, snippet, or publisher (Komdigi/Kominfo, Kemenag, Kemenkeu, Kemenko, Kementerian Investasi/BKPM, Kemendikbud/Kemendikdasmen, Kemenkes, Kemendag, Bappenas, BPS, Setkab, Pemprov/Pemkot/Pemkab, Dinas, Badan, Lembaga), else empty.

## Output columns
`No | Publisher | Publisher_Domain | Source_Type | Query_Group | Found_In_Groups | Title | Snippet | URL | Date | Keyword_Found | Also_Found_In | Source_Lang | Government_Body | Fulltext_Status | Docx_File`

## Corpus (docx) method
Each xlsx row's Google News link was resolved to the publisher URL before fetching; a link that could not be resolved is recorded as `decode_failed` and the Google interstitial is never fetched or stored. Publisher HTML is capped at 5 MB, script/style blocks are stripped, and body text is extracted with trafilatura, then readability-lxml. Pages under 300 extracted characters are `thin`; a paywall marker only marks `paywall` after extraction comes back thin. Every row is saved as `NNN_publisher_slug.docx` (Heading-1 title, metadata block with language and resolved URL, original full text) or listed in `failed.csv` with its original URL, resolved URL, reason, and stage. Row statuses are written back to the xlsx (`Fulltext_Status`, `Docx_File`). CI builds three corpus batches (`rows[index::count]`), merges them, and publishes only after a release gate verifies rows, 2025 dates, URL uniqueness, metadata completeness, and all three batches.

## Reproducibility
Each run writes `output/run-meta.json` with the run date (`run_utc`), schema version, queries, windows, per-query counts, relevance-drop samples, warnings, and errors. The merged corpus writes `corpus/corpus-meta.json` with `input_sha256`, row/ok/failed counts, per-batch summaries, and per-row results. Cite the git commit SHA plus `run_utc` from the release you used.
