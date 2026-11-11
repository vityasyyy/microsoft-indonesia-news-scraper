from src import filters


def row(**over):
    base = {
        "title": "Microsoft Indonesia",
        "snippet": "Azure cloud region",
        "url": "https://x.com/a",
        "published_raw": "Mon, 10 Mar 2025 07:00:00 GMT",
        "keyword": "k1",
        "query_group": "baseline",
        "window": "2025-01-01..2025-03-01",
        "locale": "id/ID",
        "publisher": "Kompas",
        "publisher_domain": "kompas.com",
    }
    base.update(over)
    return base


def test_keeps_2025_dedupes_url_and_merges_keywords_without_substring_bug():
    rows = [
        row(keyword="k11"),
        row(url="https://X.com/a?utm_source=x", keyword="k1"),
        row(title="Microsoft old news", url="https://x.com/old", published_raw="Mon, 10 Mar 2024 07:00:00 GMT", keyword="k1"),
    ]
    kept, stats = filters.process(rows)
    assert len(kept) == 1
    assert kept[0]["Also_Found_In"] == ["k1"]
    assert kept[0]["Found_In_Groups"] == ["baseline"]
    assert stats["dropped_not_2025"] == 1
    assert stats["duplicates"] == 1


def test_duplicate_from_second_group_extends_found_in_groups():
    rows = [
        row(keyword="baseline q", query_group="baseline"),
        row(keyword="government q", query_group="government"),
    ]
    kept, _ = filters.process(rows)
    assert len(kept) == 1
    assert kept[0]["Query_Group"] == "baseline"
    assert kept[0]["Found_In_Groups"] == ["baseline", "government"]
    assert kept[0]["Also_Found_In"] == ["government q"]


def test_relevance_gate_drops_rows_without_microsoft_signal():
    rows = [
        row(title="Harga emas naik", snippet="Pasar modal melemah"),
        row(title="Microsoft Indonesia", snippet="Azure"),
    ]
    kept, stats = filters.process(rows)
    assert len(kept) == 1
    assert stats["dropped_irrelevant"] == 1
    assert stats["dropped_irrelevant_samples"] == ["Harga emas naik"]


def test_relevance_signal_is_case_insensitive_and_checks_snippet():
    rows = [row(title="Cloud region", snippet="MICROSOFT membangun pusat data")]
    kept, _ = filters.process(rows)
    assert len(kept) == 1


def test_language_unknown_is_not_coerced_to_id():
    rows = [row(title="microsoft", snippet="")]
    kept, _ = filters.process(rows)
    assert kept[0]["Source_Lang"] == "unknown"


def test_language_other_is_labeled_other():
    rows = [row(title="Microsoft et le gouvernement francais annoncent un partenariat", snippet="")]
    kept, _ = filters.process(rows)
    assert kept[0]["Source_Lang"] == "other"


def test_government_classification_and_body_from_publisher_and_snippet():
    rows = [
        row(
            title="Microsoft kerja sama dengan Kominfo",
            snippet="Kementerian Komunikasi dan Digital mendukung Azure",
            publisher="Kominfo",
            publisher_domain="kominfo.go.id",
            url="https://x.com/gov",
        )
    ]
    kept, _ = filters.process(rows)
    assert kept[0]["Source_Type"] == "government"
    assert kept[0]["Government_Body"] == "Komdigi"


def test_government_body_prefers_specific_alias_before_generic():
    rows = [row(title="Microsoft dukung Badan Pusat Statistik", snippet="", publisher_domain="bps.go.id")]
    kept, _ = filters.process(rows)
    assert kept[0]["Government_Body"] == "BPS"


def test_government_body_empty_when_no_alias():
    kept, _ = filters.process([row(title="Microsoft Indonesia", snippet="Azure")])
    assert kept[0]["Government_Body"] == ""


def test_source_type_other_for_non_go_id():
    kept, _ = filters.process([row(publisher_domain="kompas.com")])
    assert kept[0]["Source_Type"] == "other"


def test_normalize_url_drops_all_query_params_for_google_news():
    url = "https://news.google.com/rss/articles/ABC?hl=id&gl=ID&ceid=ID:id&oc=5"
    assert filters.normalize_url(url) == "https://news.google.com/rss/articles/ABC"


def test_normalize_url_sorts_non_google_params_and_strips_only_tracking():
    url = "https://Example.com/a?b=2&a=1&utm_source=x&hl=id"
    assert filters.normalize_url(url) == "https://example.com/a?a=1&b=2&hl=id"


def test_normalize_url_removes_trailing_slash():
    assert filters.normalize_url("https://kompas.com/a/") == "https://kompas.com/a"


def test_per_query_stats_reconcile():
    rows = [
        row(keyword="q1", title="Microsoft A"),
        row(keyword="q1", title="Harga emas", snippet="Pasar modal melemah"),
        row(keyword="q2", title="Microsoft B", url="https://x.com/b", locale="en-US/US"),
    ]
    kept, stats = filters.process(rows)
    assert len(kept) == 2
    per = {(p["keyword"], p["locale"]): p for p in stats["per_query"]}
    assert per[("q1", "id/ID")]["raw"] == 2
    assert per[("q1", "id/ID")]["kept"] == 1
    assert per[("q1", "id/ID")]["dropped_irrelevant"] == 1
    assert per[("q2", "en-US/US")]["kept"] == 1
    assert stats["kept"] == 2
