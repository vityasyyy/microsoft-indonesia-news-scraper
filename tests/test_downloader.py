from unittest.mock import patch

import pytest

from src import downloader

HTML = "<html><body><article><p>" + "Berita tentang Microsoft di Indonesia. " * 30 + "</p></article></body></html>"


class Response:
    def __init__(self, html=HTML, status=200, payload=None):
        self.status_code = status
        self.encoding = "utf-8"
        self._payload = payload if payload is not None else html.encode("utf-8")

    def iter_content(self, chunk_size=65536):
        yield self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_fetch_ok_via_trafilatura_sets_resolved_url():
    with patch("src.downloader._get", return_value=Response()):
        result = downloader.fetch("https://example.com/a")
    assert result["ok"] is True
    assert len(result["text"]) >= downloader.MIN_CHARS
    assert result["reason"] == ""
    assert result["stage"] == "trafilatura"
    assert result["resolved_url"] == "https://example.com/a"


def test_google_decode_failure_never_fetches_interstitial():
    url = "https://news.google.com/rss/articles/CBMiXYZ"
    with patch("src.downloader._decode", side_effect=Exception("nope")):
        with patch("src.downloader._get") as get:
            result = downloader.fetch(url)
    get.assert_not_called()
    assert result["ok"] is False
    assert result["reason"] == "decode_failed"
    assert result["resolved_url"] == ""


def test_resolve_returns_publisher_url_and_empty_error():
    with patch("src.downloader._decode", return_value="https://publisher.com/article"):
        target, error = downloader.resolve("https://news.google.com/rss/articles/CBMiXYZ")
    assert target == "https://publisher.com/article"
    assert error == ""


def test_resolve_passthrough_publisher_url():
    target, error = downloader.resolve("https://publisher.com/article")
    assert target == "https://publisher.com/article"
    assert error == ""


def test_non_http_url_is_rejected_without_fetch():
    with patch("src.downloader._get") as get:
        result = downloader.fetch("file:///etc/passwd")
    get.assert_not_called()
    assert result["ok"] is False
    assert result["reason"] == "fetch_error"


def test_paywall_only_after_extraction_is_thin():
    html = "<html><body><p>Silakan berlangganan untuk lanjutkan membaca artikel ini.</p></body></html>"
    with patch("src.downloader._get", return_value=Response(html)):
        result = downloader.fetch("https://example.com/pay")
    assert result["ok"] is False
    assert result["reason"] == "paywall"


def test_paywall_marker_with_extracted_body_is_kept():
    html = (
        "<html><body><nav>Berlangganan</nav><article><p>"
        + "Berita lengkap tentang Microsoft dan pusat data di Indonesia. " * 30
        + "</p></article></body></html>"
    )
    with patch("src.downloader._get", return_value=Response(html)):
        result = downloader.fetch("https://example.com/long")
    assert result["ok"] is True


def test_thin_page_without_marker():
    html = "<html><body><p>Halaman kosong.</p></body></html>"
    with patch("src.downloader._get", return_value=Response(html)):
        result = downloader.fetch("https://example.com/thin")
    assert result["ok"] is False
    assert result["reason"] == "thin"


def test_script_and_style_stripped_before_extraction():
    captured = {}

    def fake_extract(html, **kwargs):
        captured["html"] = html
        return "Microsoft " * 100

    html = "<html><head><script>evil()</script><style>.x{}</style></head><body><p>ok</p></body></html>"
    with patch("src.downloader._get", return_value=Response(html)):
        with patch("src.downloader.trafilatura.extract", side_effect=fake_extract):
            downloader.fetch("https://example.com/clean")
    assert "evil()" not in captured["html"]
    assert ".x{}" not in captured["html"]


def test_oversized_response_is_capped():
    payload = b"x" * (downloader.MAX_BYTES + 1)
    with patch("src.downloader._get", return_value=Response(payload=payload)):
        result = downloader.fetch("https://example.com/huge")
    assert result["ok"] is False
    assert result["reason"] == "fetch_error"


def test_default_latin1_encoding_does_not_mojibake_utf8_pages():
    response = Response(payload="Microsoft — Komdigi".encode("utf-8"))
    response.encoding = "ISO-8859-1"
    assert "—" in downloader._read_html(response)


@pytest.mark.parametrize(
    ("status", "reason"), [(401, "blocked"), (403, "blocked"), (404, "removed")]
)
def test_http_status_reasons(status, reason):
    with patch("src.downloader._get", return_value=Response(status=status)):
        result = downloader.fetch("https://example.com/x")
    assert result["ok"] is False
    assert result["reason"] == reason
