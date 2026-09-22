# Methodology Note — Microsoft Indonesia 2025 News Corpus

## Source
Articles were collected from Google News RSS search (`news.google.com/rss/search`), no API keys required. Queries ran in two locales: Indonesian (`hl=id, gl=ID, ceid=ID:id`) and English (`hl=en-US, gl=US, ceid=US:en`).

## Keywords (4, exact)
1. `kerja sama microsoft dengan pemerintah indonesia di tahun 2025`
2. `investasi microsoft di Indonesia tahun 2025`
3. `Indonesia central cloud region (2025)`
4. `Microsoft elevAIte di Indonesia 2025`

## Date filter (strict 2025)
Only articles dated `2025-01-01` to `2025-12-31` inclusive were kept. Items with unparseable or out-of-range dates were dropped; no 2026 leakage.

## Dedupe rule
URLs were normalized (lowercased host, tracking params stripped, trailing slash removed; Google News links kept as-is). The first-seen article was kept; repeats found under other keywords were recorded in `Also_Found_In` instead of creating new rows.

## Translation rule
Article language was detected (Indonesian or English). English titles and snippets were translated to Indonesian (EN→ID via GoogleTranslator); the original English text was always preserved alongside the translation. Indonesian articles were kept as-is.

## Output columns
`No | Publisher | Title_ID | Title_Original | URL | Date | Keyword_Found | Also_Found_In | Snippet_ID | Snippet_Original | Source_Lang | translation_ok`

## Reproducibility
Each run writes `output/run-meta.json` with the run date (`run_utc`), keywords, and fetch/filter/translation counts. Cite the run with the git commit SHA plus `run_utc` from that file. (Run date: fill in after first real run.)
