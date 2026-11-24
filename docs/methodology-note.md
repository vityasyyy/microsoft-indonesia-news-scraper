# Methodology Note — Microsoft Indonesia 2025 News Corpus

This repo produces two explicitly labeled samples from Google News RSS:

- **Fresh (`scrape`, schema v3):** 15 queries across 2025, with a Microsoft relevance gate that drops non-signal candidates.
- **Legacy (`legacy`, schema v3):** the frozen original 180-row candidate list from release `articles-2025-4`, with no relevance deletion and no translation.

Both use the same xlsx columns, relevance labels, and docx corpus method. The sections below mark which rules belong to which sample.

## Source
Articles were collected from Google News RSS search (`news.google.com/rss/search`), no API keys required. Queries ran in two locales: Indonesian (`hl=id, gl=ID, ceid=ID:id`) and English (`hl=en-US, gl=US, ceid=US:en`).

## Fresh sample queries (15)
Baseline group:
1. `kerja sama microsoft dengan pemerintah indonesia di tahun 2025`
2. `investasi microsoft di Indonesia tahun 2025`
3. `Indonesia central cloud region microsoft (2025)`
4. `Microsoft elevAIte di Indonesia 2025`

Government group (Microsoft-related only):
`microsoft kementerian` · `microsoft komdigi` · `microsoft kementerian komunikasi dan digital` · `microsoft kemenag` · `microsoft kementerian investasi` · `microsoft kemenko perekonomian` · `microsoft kementerian keuangan` · `microsoft kementerian pendidikan` · `microsoft pemerintah daerah` · `microsoft pemprov` · `microsoft dinas pendidikan`

Each query ran with `after:`/`before:` for six two-month windows covering 2025 (`2025-01-01`–`2025-03-01`, `2025-03-01`–`2025-05-01`, …, `2025-11-01`–`2026-01-01`) in both locales. `run-meta.json` records raw/kept/dropped counts per query, window, and locale (including empty-URL, date, relevance, and duplicate drops), plus any query errors.

## Fresh date and URL filter (strict 2025)
Only articles dated `2025-01-01` to `2025-12-31` inclusive were kept. Items with unparseable or out-of-range dates were dropped and counted; no 2026 leakage. Rows with an empty URL were dropped and counted as `dropped_bad_url`. The legacy sample was already filtered to strict 2025 before the `articles-2025-4` release and is imported without re-filtering.

## Fresh Microsoft relevance gate
Only rows whose HTML-cleaned title or snippet contained a Microsoft signal were kept: `microsoft`, `azure`, `microsoft 365`, `office 365`, `copilot`, `linkedin`, `github`, `elevaite`, `elevate`. Dropped rows were counted per query/window and sampled by title in `run-meta.json`. The gate applies to both baseline and government queries. Legacy import intentionally does **not** apply this gate as a deletion filter.

## Dedupe rule
Google News links were keyed with all query parameters removed. Other URLs had tracking parameters stripped and the remaining parameters sorted. The first-seen article was kept; repeats found under other queries were recorded in `Also_Found_In`, and every group that found the article was recorded in `Found_In_Groups`.

## Language rule
For the fresh sample, language was detected on HTML-cleaned title+snippet text and labeled `id`, `en`, `other`, or `unknown`. Detection is seeded for reproducibility. For the legacy sample, `Source_Lang` was preserved from the frozen asset instead of re-detected. In both samples the title and body are stored as published; the snippet is HTML-cleaned. English stays English, Indonesian stays Indonesian. There is no machine translation. An `unknown` detection is never coerced to `id`.

## Classification
For the fresh sample, `Source_Type` is `government` when the publisher host from the RSS `<source url=...>` link ends with `.go.id`, otherwise `other`. For the legacy sample, `Source_Type` is `government` when the `Publisher` title matches a ministry/agency alias, otherwise `other`; after the corpus resolves the publisher URL, a `.go.id` domain upgrades the row to `government`. In both samples, `Government_Body` records the first matched ministry/agency alias from the title, snippet, or publisher (Komdigi/Kominfo, Kemenag, Kemenkeu, Kemenko, Kementerian Investasi/BKPM, Kemendikbud/Kemendikdasmen, Kemenkes, Kemendag, Bappenas, BPS, Setkab, Pemprov/Pemkot/Pemkab, Dinas, Badan, Lembaga), else empty.

## Output columns (schema v3)
`No | Publisher | Publisher_Domain | Source_Type | Query_Group | Found_In_Groups | Title | Snippet | URL | Date | Keyword_Found | Also_Found_In | Source_Lang | Microsoft_Signal | Microsoft_Mention | Analysis_Ready | Government_Body | Fulltext_Status | Docx_File`

## Legacy 180 sample (`articles-2025-4`)
The legacy sample is the original recall-first candidate list, preserved exactly rather than rescraped. Selection before that release: the four original queries (`kerja sama microsoft dengan pemerintah indonesia di tahun 2025` · `investasi microsoft di Indonesia tahun 2025` · `Indonesia central cloud region (2025)` · `Microsoft elevAIte di Indonesia 2025`), strict 2025 dates, URL dedupe, and **no relevance deletion**. The import verifies the exact asset SHA-256 and 180 rows, then maps the old headers without touching the original-language text: `Title = Title_Original`, `Snippet = clean_html(Snippet_Original)`, `Query_Group = Found_In_Groups = legacy`, `Publisher_Domain` starts empty. A blank `Title_Original` is rejected rather than falling back to the translated column.

Observed counts in `output/run-meta.json` for the frozen asset (sha256 `1a7bb86a…`): 180 rows; `Microsoft_Signal` 91 yes / 89 no; `Source_Lang` 113 `id` / 65 `en` / 2 `unknown`; 4 rows classified government from the publisher title. Because all rows are kept, this is a recall-first sampling frame, **not** a Microsoft-only list.

The three relevance labels make the analysis sample explicit:

- `Microsoft_Signal` — `yes` when the title or snippet contains a Microsoft signal, else `no`. Computed at import for legacy rows; fresh kept rows are `yes`.
- `Microsoft_Mention` — `yes`/`no` after the corpus fetches the full text and checks title+body; `unknown` when the fetch failed. Fresh rows start `unknown` until the corpus runs.
- `Analysis_Ready` — `yes` when signal is `yes` or mention is `yes`; `no` when signal is `no` and mention is `no`; `review` when signal is `no` and mention is `unknown` (blocked, paywalled, or otherwise unfetched).

Local runs of the frozen asset typically produce about 145 ok / 35 failed rows out of 180; exact per-run mention, analysis, and failure counts live in `corpus/corpus-meta.json` and vary as publisher pages change. The release gate is the authority for the published run.

Run it with `make legacy` (fetch + import) and `make corpus`; in CI, the manual-only `legacy` workflow does the same in three batches and publishes `articles-2025-legacy-<n>`.

## Corpus (docx) method
Each xlsx row's Google News link was resolved to the publisher URL before fetching; a link that could not be resolved is recorded as `decode_failed` and the Google interstitial is never fetched or stored. Publisher HTML is capped at 5 MB, script/style blocks are stripped, and body text is extracted with trafilatura, then readability-lxml. Pages under 300 extracted characters are `thin`; a paywall marker only marks `paywall` after extraction comes back thin. Every row is saved as `NNN_<publisher-slug>_<title-slug>.docx` (Heading-1 title, metadata block with language, Microsoft mention, analysis-ready, and resolved URL, extracted full text) or listed in `failed.csv` with its original URL, resolved URL, reason, and stage. Row statuses, mention, analysis, and a resolved publisher domain (when the cell is empty) are written back to the xlsx (`Fulltext_Status`, `Docx_File`, `Microsoft_Mention`, `Analysis_Ready`, `Publisher_Domain`). CI builds three corpus batches (`rows[index::count]`, up to two at a time), merges them, and publishes only after a release gate verifies rows, dates, URL uniqueness, allowed relevance flag values, metadata completeness, status/docx consistency, and all three batches. The gate does not require every legacy row to be Microsoft-relevant.

## Reproducibility
Each run writes `output/run-meta.json`. Fresh runs contain the run date (`run_utc`), schema version, queries, windows, per-query counts, relevance-drop samples, warnings, and errors. Legacy runs contain `run_utc`, `schema_version`, `mode=legacy`, the exact `source_release`, `source_asset_url`, `source_sha256`, row/signal/language/government counts, and `errors`. The merged corpus writes `corpus/corpus-meta.json` with `input_sha256` (the xlsx hash every batch was built from), `released_xlsx_sha256` (the post-status-write-back hash), row/ok/failed counts, mention/analysis counts, per-batch summaries, and per-row results; merge refuses batches whose `input_sha256` does not match the xlsx. Cite the git commit SHA plus `run_utc` from the release you used.
