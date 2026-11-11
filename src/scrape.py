"""Entry: scrape Microsoft-related 2025 news -> schema v2 xlsx + run-meta."""
import datetime
import pathlib

from src import exporter, fetcher, filters

# Baseline keeps the four original method-traceable queries. The cloud-region
# query now names Microsoft explicitly: a 2025-01-01..2025-03-01 probe returned
# 2 relevant rows from 4 raw (vs 2 from 11 for the old wording).
BASELINE_QUERIES = [
    "kerja sama microsoft dengan pemerintah indonesia di tahun 2025",
    "investasi microsoft di Indonesia tahun 2025",
    "Indonesia central cloud region microsoft (2025)",
    "Microsoft elevAIte di Indonesia 2025",
]

GOVERNMENT_QUERIES = [
    "microsoft kementerian",
    "microsoft komdigi",
    "microsoft kementerian komunikasi dan digital",
    "microsoft kemenag",
    "microsoft kementerian investasi",
    "microsoft kemenko perekonomian",
    "microsoft kementerian keuangan",
    "microsoft kementerian pendidikan",
    "microsoft pemerintah daerah",
    "microsoft pemprov",
    "microsoft dinas pendidikan",
]

WINDOWS = [
    ("2025-01-01", "2025-03-01"),
    ("2025-03-01", "2025-05-01"),
    ("2025-05-01", "2025-07-01"),
    ("2025-07-01", "2025-09-01"),
    ("2025-09-01", "2025-11-01"),
    ("2025-11-01", "2026-01-01"),
]

OUT_XLSX = "output/articles-2025.xlsx"
OUT_META = "output/run-meta.json"


def planned_queries():
    return [("baseline", query) for query in BASELINE_QUERIES] + [
        ("government", query) for query in GOVERNMENT_QUERIES
    ]


def _counts(rows, key):
    counts = {}
    for row in rows:
        value = row.get(key)
        if value:
            counts[value] = counts.get(value, 0) + 1
    return counts


def _groups(value):
    if isinstance(value, (list, tuple)):
        return value
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def build_meta(fetch_total, stats, report, kept=None):
    kept = kept or []
    per_query = {(row["keyword"], row["window"], row["locale"]): row for row in stats["per_query"]}
    queries = []
    for entry in report["queries"]:
        key = (entry["keyword"], entry["window"], entry["locale"])
        counts = per_query.get(key, {})
        queries.append(
            {
                **entry,
                "kept": counts.get("kept", 0),
                "dropped_not_2025": counts.get("dropped_not_2025", 0),
                "dropped_bad_date": counts.get("dropped_bad_date", 0),
                "dropped_bad_url": counts.get("dropped_bad_url", 0),
                "dropped_irrelevant": counts.get("dropped_irrelevant", 0),
                "duplicates": counts.get("duplicates", 0),
            }
        )
    return {
        "run_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "schema_version": 2,
        "queries": queries,
        "windows": [f"{start}..{end}" for start, end in WINDOWS],
        "keywords": [query for _, query in planned_queries()],
        "fetch_total": fetch_total,
        "kept": stats["kept"],
        "gov_rows": sum(1 for row in kept if row.get("Source_Type") == "government"),
        "gov_domains": sorted(
            {
                row.get("Publisher_Domain")
                for row in kept
                if row.get("Source_Type") == "government" and row.get("Publisher_Domain")
            }
        ),
        "by_government_body": _counts(kept, "Government_Body"),
        "by_source_type": _counts(kept, "Source_Type"),
        "by_query_group": _counts(kept, "Query_Group"),
        "by_language": _counts(kept, "Source_Lang"),
        "found_in_government": sum(
            1 for row in kept if "government" in _groups(row.get("Found_In_Groups"))
        ),
        "dropped_not_2025": stats["dropped_not_2025"],
        "dropped_bad_date": stats["dropped_bad_date"],
        "dropped_bad_url": stats.get("dropped_bad_url", 0),
        "dropped_irrelevant": stats["dropped_irrelevant"],
        "duplicates": stats["duplicates"],
        "dropped_irrelevant_samples": stats["dropped_irrelevant_samples"],
        "warnings": report["warnings"],
        "errors": [entry for entry in queries if entry["error"]],
    }


def main():
    pathlib.Path("output").mkdir(parents=True, exist_ok=True)
    rows, report = fetcher.fetch_all(planned_queries(), WINDOWS)
    kept, stats = filters.process(rows)
    meta = build_meta(len(rows), stats, report, kept)
    exporter.write_meta(meta, OUT_META)
    if not kept:
        print(f"fetched={len(rows)} kept=0: no Microsoft-relevant 2025 rows; refusing to write {OUT_XLSX}")
        return 1
    exporter.export_xlsx(kept, OUT_XLSX)
    print(
        f"fetched={len(rows)} kept={len(kept)} "
        f"dropped_irrelevant={stats['dropped_irrelevant']} xlsx={OUT_XLSX}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
