from src import filters

def test_keeps_2025_dedupes_url():
    rows = [
        {"title": "A", "url": "https://Kompas.com/a?utm_source=x", "published_raw": "Mon, 10 Mar 2025 07:00:00 GMT", "keyword": "k1", "publisher": "Kompas", "snippet": "s", "locale": "id/ID"},
        {"title": "A dup", "url": "https://kompas.com/a", "published_raw": "Tue, 11 Mar 2025 07:00:00 GMT", "keyword": "k2", "publisher": "Kompas", "snippet": "s", "locale": "en-US/US"},
        {"title": "Old", "url": "https://x.com/old", "published_raw": "Mon, 10 Mar 2024 07:00:00 GMT", "keyword": "k1", "publisher": "X", "snippet": "s", "locale": "id/ID"},
    ]
    kept, stats = filters.dedupe(rows)
    urls = [r["url"] for r in kept]
    assert len(kept) == 1
    assert stats["dropped_not_2025"] == 1
    assert stats["duplicates"] == 1
    assert kept[0]["Also_Found_In"] == "k2"
    assert kept[0]["date_iso"].startswith("2025-03-10")
