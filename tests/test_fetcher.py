from unittest.mock import patch

import pytest

from src import fetcher

SAMPLE_RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>test</title>
<item><title>Microsoft investasi di Indonesia - Kompas</title>
<link>https://news.google.com/rss/articles/abc?hl=id</link>
<source url="https://kompas.com">Kompas</source>
<pubDate>Mon, 10 Mar 2025 07:00:00 GMT</pubDate>
<description>&lt;a href="x"&gt;Snippet here&lt;/a&gt;</description></item>
</channel></rss>"""


class FakeResp:
    status_code = 200
    text = SAMPLE_RSS

    def raise_for_status(self):
        pass


def test_build_query_adds_two_month_window():
    assert (
        fetcher.build_query("microsoft indonesia", ("2025-01-01", "2025-03-01"))
        == "microsoft indonesia after:2025-01-01 before:2025-03-01"
    )


def test_fetch_window_parses_fields_and_publisher_domain():
    with patch("src.fetcher._get", return_value=FakeResp()):
        rows = fetcher.fetch_window(
            "baseline", "investasi microsoft", ("2025-01-01", "2025-03-01"), "id", "ID", "ID:id"
        )
    assert len(rows) == 1
    assert rows[0]["publisher"] == "Kompas"
    assert rows[0]["publisher_domain"] == "kompas.com"
    assert rows[0]["keyword"] == "investasi microsoft"
    assert rows[0]["query_group"] == "baseline"
    assert rows[0]["window"] == "2025-01-01..2025-03-01"
    assert rows[0]["locale"] == "id/ID"


def test_fetch_all_records_error_and_continues():
    calls = []

    def fake_fetch(group, keyword, window, hl, gl, ceid, retries=3):
        calls.append(keyword)
        if keyword == "bad":
            raise RuntimeError("boom")
        return [
            {
                "title": "x",
                "keyword": keyword,
                "window": f"{window[0]}..{window[1]}",
                "locale": f"{hl}/{gl}",
                "query_group": group,
            }
        ]

    with patch("src.fetcher.fetch_window", side_effect=fake_fetch), patch("src.fetcher.time.sleep"):
        rows, report = fetcher.fetch_all(
            [("baseline", "good"), ("government", "bad")],
            [("2025-01-01", "2025-03-01")],
            locales=[("id", "ID", "ID:id")],
        )
    assert len(rows) == 1
    assert calls == ["good", "bad"]
    assert report["queries"][0]["raw"] == 1
    assert report["queries"][0]["error"] == ""
    assert report["queries"][1]["raw"] == 0
    assert report["queries"][1]["error"] == "boom"


def test_fetch_all_warns_when_window_hits_rss_cap():
    with patch("src.fetcher.fetch_window", return_value=[{}] * fetcher.RSS_CAP), patch(
        "src.fetcher.time.sleep"
    ):
        _, report = fetcher.fetch_all(
            [("baseline", "q")],
            [("2025-01-01", "2025-03-01")],
            locales=[("id", "ID", "ID:id")],
        )
    assert report["queries"][0]["capped"] is True
    assert any("cap" in w for w in report["warnings"])


def test_retry_does_not_sleep_after_final_attempt():
    sleeps = []
    with patch("src.fetcher.time.sleep", side_effect=sleeps.append), patch(
        "src.fetcher._get", side_effect=RuntimeError("nope")
    ):
        with pytest.raises(RuntimeError):
            fetcher.fetch_window(
                "baseline", "q", ("2025-01-01", "2025-03-01"), "id", "ID", "ID:id", retries=3
            )
    assert sleeps == [2, 4]


class BozoResp:
    status_code = 200
    text = "<html><body>Access denied"

    def raise_for_status(self):
        pass


def test_fetch_all_records_error_for_bozo_empty_feed():
    with patch("src.fetcher._get", return_value=BozoResp()), patch("src.fetcher.time.sleep"):
        rows, report = fetcher.fetch_all(
            [("baseline", "q")],
            [("2025-01-01", "2025-03-01")],
            locales=[("id", "ID", "ID:id")],
            delay_s=0,
        )
    assert rows == []
    assert "malformed" in report["queries"][0]["error"]
