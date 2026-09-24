.PHONY: corpus corpus-test corpus-zip help

corpus: ## Full local corpus build (reads output/articles-2025.xlsx)
	uv run python -m src.make_corpus

corpus-test: ## Fast iteration on first N rows (default 5): make corpus-test LIMIT=10
	uv run python -m src.make_corpus

corpus-zip: ## Zip corpus/ + failed.csv + meta for sending
	./scripts/zip_corpus.sh

help: ## List targets
	@grep -E '^[a-z-]+: ## ' Makefile
