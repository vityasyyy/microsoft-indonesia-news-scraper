import pathlib

from src import scrape


def test_baseline_group_has_four_queries_with_explicit_microsoft_variant():
    assert len(scrape.BASELINE_QUERIES) == 4
    assert any("cloud region" in q.lower() and "microsoft" in q.lower() for q in scrape.BASELINE_QUERIES)
    assert not any(q == "Indonesia central cloud region (2025)" for q in scrape.BASELINE_QUERIES)


def test_government_group_is_microsoft_targeted():
    assert len(scrape.GOVERNMENT_QUERIES) == 11
    assert all(q.startswith("microsoft ") for q in scrape.GOVERNMENT_QUERIES)
    assert "microsoft komdigi" in scrape.GOVERNMENT_QUERIES


def test_planned_queries_tag_groups():
    queries = scrape.planned_queries()
    assert sum(1 for group, _ in queries if group == "baseline") == 4
    assert sum(1 for group, _ in queries if group == "government") == 11


def test_windows_cover_2025_in_two_month_blocks():
    assert scrape.WINDOWS == [
        ("2025-01-01", "2025-03-01"),
        ("2025-03-01", "2025-05-01"),
        ("2025-05-01", "2025-07-01"),
        ("2025-07-01", "2025-09-01"),
        ("2025-09-01", "2025-11-01"),
        ("2025-11-01", "2026-01-01"),
    ]


def test_build_meta_merges_fetch_and_filter_stats():
    report = {
        "queries": [
            {
                "group": "baseline",
                "keyword": "q",
                "window": "2025-01-01..2025-03-01",
                "locale": "id/ID",
                "raw": 5,
                "capped": False,
                "error": "",
            }
        ],
        "warnings": [],
    }
    stats = {
        "kept": 2,
        "dropped_not_2025": 1,
        "dropped_bad_date": 0,
        "dropped_irrelevant": 2,
        "duplicates": 0,
        "dropped_irrelevant_samples": ["noise"],
        "per_query": [
            {
                "group": "baseline",
                "keyword": "q",
                "window": "2025-01-01..2025-03-01",
                "locale": "id/ID",
                "raw": 5,
                "kept": 2,
                "dropped_not_2025": 1,
                "dropped_bad_date": 0,
                "dropped_irrelevant": 2,
                "duplicates": 0,
            }
        ],
    }
    meta = scrape.build_meta(5, stats, report)
    assert meta["schema_version"] == 2
    assert meta["fetch_total"] == 5
    assert meta["kept"] == 2
    assert meta["queries"][0]["raw"] == 5
    assert meta["queries"][0]["kept"] == 2
    assert meta["queries"][0]["dropped_irrelevant"] == 2
    assert meta["dropped_irrelevant_samples"] == ["noise"]


def test_build_meta_keeps_failed_query_rows():
    report = {
        "queries": [
            {
                "group": "government",
                "keyword": "q",
                "window": "2025-01-01..2025-03-01",
                "locale": "id/ID",
                "raw": 0,
                "capped": False,
                "error": "boom",
            }
        ],
        "warnings": [],
    }
    stats = {
        "kept": 0,
        "dropped_not_2025": 0,
        "dropped_bad_date": 0,
        "dropped_irrelevant": 0,
        "duplicates": 0,
        "dropped_irrelevant_samples": [],
        "per_query": [],
    }
    meta = scrape.build_meta(0, stats, report)
    assert meta["queries"][0]["error"] == "boom"
    assert meta["queries"][0]["kept"] == 0
    assert meta["errors"][0]["keyword"] == "q"


def test_zero_usable_rows_fails_before_writing_xlsx(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    empty_report = {"queries": [], "warnings": []}
    zero_stats = {
        "fetched": 0,
        "kept": 0,
        "dropped_not_2025": 0,
        "dropped_bad_date": 0,
        "dropped_irrelevant": 0,
        "duplicates": 0,
        "dropped_irrelevant_samples": [],
        "per_query": [],
    }
    monkeypatch.setattr(scrape.fetcher, "fetch_all", lambda *a, **k: ([], empty_report))
    monkeypatch.setattr(scrape.filters, "process", lambda rows: ([], zero_stats))
    assert scrape.main() == 1
    assert not pathlib.Path("output/articles-2025.xlsx").exists()
    assert pathlib.Path("output/run-meta.json").exists()
