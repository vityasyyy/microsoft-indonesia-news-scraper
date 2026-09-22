"""Entry: scrape 4 keywords -> 2025-only deduped translated xlsx."""
import datetime
import pathlib
from src import fetcher, filters, translator, exporter

KEYWORDS = [
    "kerja sama microsoft dengan pemerintah indonesia di tahun 2025",
    "investasi microsoft di Indonesia tahun 2025",
    "Indonesia central cloud region (2025)",
    "Microsoft elevAIte di Indonesia 2025",
]
OUT_XLSX = "output/articles-2025.xlsx"
OUT_META = "output/run-meta.json"

def main():
    pathlib.Path("output").mkdir(parents=True, exist_ok=True)
    raw = fetcher.fetch_all(KEYWORDS)
    kept, dstats = filters.dedupe(raw)
    enriched, tstats = translator.enrich(kept)
    exporter.export_xlsx(enriched, OUT_XLSX)
    meta = {
        "run_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "keywords": KEYWORDS,
        "fetch_total": len(raw),
        **dstats,
        **tstats,
    }
    exporter.write_meta(meta, OUT_META)
    print(f"fetched={len(raw)} kept={len(enriched)} xlsx={OUT_XLSX}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
