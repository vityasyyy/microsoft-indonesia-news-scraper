# Docs Index

How docs work in this repo (for everyone, including non-technical readers):

- `docs/active/` — docs for work currently in progress (draft designs, plans being built).
- `docs/completed/` — finished or superseded docs (approved designs, methodology notes, historical plans).
- This `README.md` — the map to everything.

## Current docs

- [Article Scrape Pipeline — Design Spec (completed)](completed/2026-09-22-article-scrape-pipeline-design.md) — Phase 1 xlsx inventory design. Historical: describes the original translation-era schema; the current schema and rules are in the README and methodology note.
- [Article Scrape Pipeline — Implementation Plan (completed)](completed/2026-09-22-article-scrape-pipeline.md) — step-by-step build plan for Phase 1 (historical).
- [Methodology Note](methodology-note.md) — citable research appendix: sources, 15 queries, 2025 filter, relevance gate, dedupe, language labeling (no translation), corpus method, reproducibility.
- [DOCX Corpus Pipeline — Design Spec (completed, superseded)](completed/2026-09-24-docx-corpus-pipeline-design.md) — Phase 2 design. Machine translation was removed on 2026-11-11; see the superseded note in the file.
- [DOCX Corpus Pipeline — Implementation Plan (completed)](completed/2026-09-24-docx-corpus-pipeline.md) — historical execution plan for Phase 2.

## Lifecycle

1. New idea → draft in `docs/active/`.
2. Reviewed + approved → move to `docs/completed/` (via `git mv`).
3. Update this index with a link + one-line summary.
