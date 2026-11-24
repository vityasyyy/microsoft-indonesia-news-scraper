.PHONY: corpus corpus-test corpus-merge corpus-zip legacy help

LIMIT ?= 5

legacy: ## Fetch the frozen articles-2025-4 asset and import the 180-row list
	./scripts/fetch_legacy.sh
	uv run python -m src.import_legacy --input output/legacy/articles-2025-4.xlsx --out output/articles-2025.xlsx

corpus: ## Full local corpus build (reads output/articles-2025.xlsx)
	uv run python -m src.make_corpus

corpus-test: ## Fast iteration on first N rows (default 5): make corpus-test LIMIT=10
	LIMIT=$(LIMIT) uv run python -m src.make_corpus

corpus-merge: ## Merge corpus-batch-*/ into one corpus/
	uv run python -m src.merge_corpus --batches $(wildcard corpus-batch-*) --out corpus --xlsx output/articles-2025.xlsx

corpus-zip: ## Zip corpus/ + failed.csv + meta for sending
	./scripts/zip_corpus.sh

help: ## List targets
	@grep -E '^[a-z-]+: ## ' Makefile
