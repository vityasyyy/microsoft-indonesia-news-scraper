import socket
import time
from unittest.mock import patch

import pytest

from src import downloader

HTML = "<html><body><article><p>" + "Berita tentang Microsoft di Indonesia. " * 30 + "</p></article></body></html>"
PUBLIC_IP = "93.184.216.34"


@pytest.fixture(autouse=True)
def stub_dns(monkeypatch):
    def getaddrinfo(host, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_IP, 0))]

    monkeypatch.setattr(downloader.socket, "getaddrinfo", getaddrinfo)


class Response:
    def __init__(self, html=HTML, status=200, payload=None, headers=None):
        self.status_code = status
        self.encoding = "utf-8"
        self._payload = payload if payload is not None else html.encode("utf-8")
        self.headers = headers or {}
        self.closed = False

    def iter_content(self, chunk_size=65536):
        yield self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def close(self):
        self.closed = True


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


@pytest.mark.parametrize("status", [200, 401, 404])
def test_fetch_closes_streaming_response(status):
    response = Response(status=status)
    with patch("src.downloader._get", return_value=response):
        downloader.fetch("https://example.com/x")
    assert response.closed is True


def test_fetch_closes_streaming_response_when_reading_fails():
    created = []

    class Broken(Response):
        def iter_content(self, chunk_size=65536):
            raise RuntimeError("stream broke")

    def make_response(_url):
        response = Broken()
        created.append(response)
        return response

    with patch("src.downloader._get", side_effect=make_response):
        with patch("src.downloader.time.sleep"):
            result = downloader.fetch("https://example.com/broken")
    assert result["reason"] == "fetch_error"
    assert created and all(response.closed for response in created)


def test_get_disables_automatic_redirects():
    with patch("src.downloader.requests.get") as get:
        downloader._get("https://example.com/a")
    assert get.call_args.kwargs["allow_redirects"] is False


@pytest.mark.parametrize("ip", ["127.0.0.1", "169.254.169.254"])
def test_fetch_rejects_non_global_targets_without_request(ip):
    answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]
    with patch("src.downloader.socket.getaddrinfo", return_value=answers):
        with patch("src.downloader._get") as get:
            result = downloader.fetch("http://internal.example/admin")
    get.assert_not_called()
    assert result["ok"] is False
    assert result["reason"] == "fetch_error"


def test_fetch_rejects_hostname_with_any_non_global_answer():
    answers = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", (PUBLIC_IP, 0)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.7", 0)),
    ]
    with patch("src.downloader.socket.getaddrinfo", return_value=answers):
        with patch("src.downloader._get") as get:
            result = downloader.fetch("https://mixed.example/a")
    get.assert_not_called()
    assert result["reason"] == "fetch_error"


def test_fetch_blocks_redirect_to_private_host():
    redirect = Response(status=302, headers={"Location": "http://169.254.169.254/latest/meta-data"})

    def getaddrinfo(host, *args, **kwargs):
        ip = "169.254.169.254" if "169.254" in host else PUBLIC_IP
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]

    with patch("src.downloader.socket.getaddrinfo", side_effect=getaddrinfo):
        with patch("src.downloader._get", return_value=redirect) as get:
            result = downloader.fetch("https://example.com/start")
    assert get.call_count == 1
    assert redirect.closed is True
    assert result["ok"] is False
    assert result["reason"] == "fetch_error"


def test_fetch_follows_redirect_to_public_host():
    redirect = Response(status=302, headers={"Location": "https://example.com/final"})
    final = Response()
    with patch("src.downloader._get", side_effect=[redirect, final]) as get:
        result = downloader.fetch("https://example.com/start")
    assert get.call_count == 2
    assert redirect.closed is True
    assert final.closed is True
    assert result["ok"] is True
    assert result["resolved_url"] == "https://example.com/final"


def test_fetch_rejects_more_than_five_redirects():
    redirects = [Response(status=302, headers={"Location": "https://example.com/next"})] * 6
    with patch("src.downloader._get", side_effect=redirects) as get:
        result = downloader.fetch("https://example.com/start")
    assert get.call_count == 6
    assert result["reason"] == "fetch_error"


class SlowResponse(Response):
    def iter_content(self, chunk_size=65536):
        yield b"a" * 10
        time.sleep(0.02)
        yield b"b" * 10


def test_read_html_stops_at_total_deadline(monkeypatch):
    monkeypatch.setattr(downloader, "READ_DEADLINE_S", 0.01)
    assert downloader._read_html(SlowResponse()) is None


def test_fetch_maps_read_deadline_to_fetch_error(monkeypatch):
    monkeypatch.setattr(downloader, "READ_DEADLINE_S", 0.01)
    monkeypatch.setattr(downloader, "DELAY_S", 0)
    responses = []

    def get(url):
        response = SlowResponse()
        responses.append(response)
        return response

    with patch("src.downloader._get", side_effect=get):
        result = downloader.fetch("https://example.com/slow")
    assert result["reason"] == "fetch_error"
    assert responses and all(response.closed for response in responses)


def test_fetch_reports_readability_stage():
    html = "<html><body><article><p>short</p></article></body></html>"

    class FakeDocument:
        def __init__(self, source):
            self.source = source

        def summary(self):
            return "<p>" + "Microsoft readability body text. " * 30 + "</p>"

    with patch("src.downloader._get", return_value=Response(html)):
        with patch("src.downloader.trafilatura.extract", return_value="short"):
            with patch("readability.Document", FakeDocument):
                result = downloader.fetch("https://example.com/readability")
    assert result["ok"] is True
    assert result["stage"] == "readability"


def test_fetch_blocks_redirect_to_non_http_scheme():
    redirect = Response(status=302, headers={"Location": "file:///etc/passwd"})
    with patch("src.downloader._get", return_value=redirect):
        result = downloader.fetch("https://example.com/start")
    assert redirect.closed is True
    assert result["reason"] == "fetch_error"


def test_fetch_revalidates_redirect_chain_targets():
    first = Response(status=302, headers={"Location": "https://example.com/hop"})
    second = Response(status=302, headers={"Location": "http://127.0.0.1/secret"})

    def getaddrinfo(host, *args, **kwargs):
        ip = "127.0.0.1" if host == "127.0.0.1" else PUBLIC_IP
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))]

    with patch("src.downloader.socket.getaddrinfo", side_effect=getaddrinfo):
        with patch("src.downloader._get", side_effect=[first, second]) as get:
            result = downloader.fetch("https://example.com/start")
    assert get.call_count == 2
    assert result["reason"] == "fetch_error"
