# Docs Index

How docs work in this repo (for everyone, including non-technical readers):

- `docs/active/` — docs for work currently in progress (draft designs, plans being built).
- `docs/completed/` — finished, reviewed docs (approved designs, methodology notes).
- This `README.md` — the map to everything.

## Current docs

- [Article Scrape Pipeline — Design Spec (completed)](completed/2026-09-22-article-scrape-pipeline-design.md) — what we are building, why, and how (Phase 1 xlsx + Phase 2 docx preview). Approved 2026-09-22.
- [Article Scrape Pipeline — Implementation Plan (active)](active/2026-09-22-article-scrape-pipeline.md) — step-by-step build plan (Tasks 1–9).
- [Methodology Note](methodology-note.md) — 1-page thesis appendix: sources, keywords, 2025 filter, dedupe, translation, reproducibility.

## Lifecycle

1. New idea → draft in `docs/active/`.
2. Reviewed + approved → move to `docs/completed/` (via `git mv`).
3. Update this index with a link + one-line summary.
