"""Fetch one publisher article and extract its body text."""
import re
import time
import urllib.parse

import requests
import trafilatura

from src import language

MIN_CHARS = 300
MAX_WORKERS = 8
DELAY_S = 1.0
TIMEOUT_S = 10
MAX_BYTES = 5 * 1024 * 1024
USER_AGENT = "Mozilla/5.0 (news-corpus-research)"
PAYWALL_MARKERS = ("berlangganan", "paywall", "subscribe to read", "lanjutkan membaca", "akses penuh")


def _get(url, timeout=TIMEOUT_S):
    return requests.get(
        url, headers={"User-Agent": USER_AGENT}, timeout=timeout, stream=True
    )


def _is_http(url):
    try:
        parsed = urllib.parse.urlparse(url or "")
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.hostname)


def _decode(url):
    """Resolve a Google News redirect link to the publisher article URL."""
    from googlenewsdecoder import gnewsdecoder

    result = gnewsdecoder(url, interval=1)
    if isinstance(result, dict) and result.get("success") and result.get("decoded_url"):
        return result["decoded_url"]
    raise RuntimeError(f"could not decode {url}")


def resolve(url):
    """Return (target_url, error). Google failures never fall through."""
    try:
        host = (urllib.parse.urlparse(url or "").hostname or "").lower()
    except ValueError:
        return url, "fetch_error"
    if host.startswith("news.google."):
        try:
            return _decode(url), ""
        except Exception:
            return url, "decode_failed"
    return url, ""


def _read_html(response):
    chunks = []
    total = 0
    for chunk in response.iter_content(chunk_size=65536):
        if not chunk:
            continue
        total += len(chunk)
        if total > MAX_BYTES:
            return None
        chunks.append(chunk)
    encoding = getattr(response, "encoding", None) or "utf-8"
    return b"".join(chunks).decode(encoding, errors="replace")


def _paywalled(html):
    lowered = (html or "").lower()
    return any(marker in lowered for marker in PAYWALL_MARKERS)


def _extract(html):
    cleaned = language.strip_scripts(html)
    text = (trafilatura.extract(cleaned) or "").strip()
    if len(text) >= MIN_CHARS:
        return text
    try:
        from readability import Document

        text = language.clean_html(Document(cleaned).summary())
    except Exception:
        return ""
    return text if len(text) >= MIN_CHARS else ""


def fetch(url):
    """Never raise: every URL resolves to ok or a closed-set failure reason."""
    target, error = resolve(url)
    if error:
        return {"ok": False, "text": "", "reason": error, "stage": "resolve", "resolved_url": ""}
    if not _is_http(target):
        return {
            "ok": False,
            "text": "",
            "reason": "fetch_error",
            "stage": "resolve",
            "resolved_url": target,
        }
    html = ""
    for attempt in range(2):
        try:
            if attempt:
                time.sleep(DELAY_S)
            response = _get(target)
            if response.status_code in (401, 403):
                return {
                    "ok": False,
                    "text": "",
                    "reason": "blocked",
                    "stage": "fetch",
                    "resolved_url": target,
                }
            if response.status_code == 404:
                return {
                    "ok": False,
                    "text": "",
                    "reason": "removed",
                    "stage": "fetch",
                    "resolved_url": target,
                }
            response.raise_for_status()
            html = _read_html(response)
            if html is None:
                return {
                    "ok": False,
                    "text": "",
                    "reason": "fetch_error",
                    "stage": "fetch",
                    "resolved_url": target,
                }
            break
        except Exception:
            html = ""
    if not html:
        return {
            "ok": False,
            "text": "",
            "reason": "fetch_error",
            "stage": "fetch",
            "resolved_url": target,
        }
    text = _extract(html)
    if len(text) >= MIN_CHARS:
        return {"ok": True, "text": text, "reason": "", "stage": "trafilatura", "resolved_url": target}
    if _paywalled(html):
        return {
            "ok": False,
            "text": "",
            "reason": "paywall",
            "stage": "extract",
            "resolved_url": target,
        }
    return {"ok": False, "text": "", "reason": "thin", "stage": "extract", "resolved_url": target}
