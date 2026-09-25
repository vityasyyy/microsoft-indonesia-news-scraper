from unittest.mock import patch
from src import downloader

HTML = "<html><body><article><p>" + "Berita tentang Microsoft di Indonesia. " * 30 + "</p></article></body></html>"

def test_fetch_ok_via_trafilatura():
    class R:
        status_code = 200
        text = HTML
        def raise_for_status(self): pass
    with patch("src.downloader._get", return_value=R()):
        with patch("time.sleep", return_value=None):
            res = downloader.fetch("https://example.com/a")
    assert res["ok"] is True
    assert len(res["text"]) >= 300
    assert res["reason"] == ""

def test_fetch_paywall_marked_not_raised():
    class R:
        status_code = 200
        text = "<html><body>Silakan berlangganan untuk lanjutkan membaca</body></html>"
        def raise_for_status(self): pass
    with patch("src.downloader._get", return_value=R()):
        with patch("time.sleep", return_value=None):
            res = downloader.fetch("https://example.com/pay")
    assert res["ok"] is False
    assert res["reason"] == "paywall"

def test_fetch_404_marked_removed():
    import requests
    with patch("src.downloader._get", side_effect=requests.HTTPError("404")):
        with patch("time.sleep", return_value=None):
            res = downloader.fetch("https://example.com/gone")
    assert res["ok"] is False
    assert res["reason"] in ("removed", "fetch_error")

def test_resolve_decodes_google_news_url():
    with patch("src.downloader._decode", return_value="https://publisher.com/article"):
        assert downloader.resolve("https://news.google.com/rss/articles/CBMiXYZ") == "https://publisher.com/article"

def test_resolve_passthrough_publisher_url():
    assert downloader.resolve("https://publisher.com/article") == "https://publisher.com/article"

def test_resolve_fallback_on_decode_failure():
    u = "https://news.google.com/rss/articles/CBMiXYZ"
    with patch("src.downloader._decode", side_effect=Exception("nope")):
        assert downloader.resolve(u) == u

def test_fetch_resolves_before_get():
    class R:
        status_code = 200
        text = HTML
        def raise_for_status(self): pass
    seen = {}
    def fake_get(url, timeout=10):
        seen["url"] = url
        return R()
    with patch("src.downloader._decode", return_value="https://publisher.com/article"):
        with patch("src.downloader._get", side_effect=fake_get):
            with patch("time.sleep", return_value=None):
                res = downloader.fetch("https://news.google.com/rss/articles/CBMiXYZ")
    assert res["ok"] is True
    assert seen["url"] == "https://publisher.com/article"
