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
