# Microsoft Indonesia 2025 — News Article Scraper

For everyone (no coding needed): this project collects news articles about Microsoft in Indonesia from 2025 into one Excel file.

## Download (no code)
1. Open the GitHub repo page.
2. Click **Releases** (right side).
3. Open the newest `articles-2025-YYYYMMDD` release.
4. Download `articles-2025.xlsx`.
5. Open in Excel / Google Sheets.

## What's inside the Excel
No (number), Publisher, Title_ID (Indonesian title), Title_Original, URL, Date, Keyword_Found, Snippet, Source_Lang.

## For research citation
See `docs/methodology-note.md` — a 1-page method note you can quote in a paper appendix.

## Re-run it yourself (optional)
Install `uv`, then `uv sync && uv run python src/scrape.py`. Output goes to `output/`.

## For developers
- Set up the environment and run the pipeline: `uv sync && uv run python src/scrape.py`. Output goes to `output/` (`articles-2025.xlsx` + `run-meta.json`).
- Run the tests: `uv run pytest -q`.
