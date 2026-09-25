"""Fetch one article URL and extract body text via fallback chain."""
import re
import time
import requests
import trafilatura

MIN_CHARS = 300
MAX_WORKERS = 8
DELAY_S = 1.0
TIMEOUT_S = 10
USER_AGENT = "Mozilla/5.0 (news-corpus-research)"
PAYWALL_MARKERS = ("berlangganan", "paywall", "subscribe to read", "lanjutkan membaca", "akses penuh")
TAG_RE = re.compile(r"<[^>]+>")

def _get(url, timeout=TIMEOUT_S):
    return requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)

def _decode(url):
    """Resolve a Google News redirect link to the publisher article URL."""
    from googlenewsdecoder import gnewsdecoder
    res = gnewsdecoder(url, interval=1)
    if isinstance(res, dict) and res.get("success") and res.get("decoded_url"):
        return res["decoded_url"]
    raise RuntimeError(f"could not decode {url}")

def resolve(url):
    """Google News RSS links redirect to interstitial pages; resolve them first."""
    import urllib.parse
    try:
        host = (urllib.parse.urlparse(url or "").hostname or "").lower()
    except Exception:
        return url
    if host == "news.google.com":
        try:
            return _decode(url)
        except Exception:
            return url
    return url

def _clean(text):
    t = TAG_RE.sub(" ", text or "")
    return re.sub(r"\s+", " ", t).strip()

def _paywalled(html):
    low = (html or "").lower()
    return any(m in low for m in PAYWALL_MARKERS)

def fetch(url):
    target = resolve(url)
    html = ""
    for _ in range(2):
        try:
            time.sleep(DELAY_S)
            r = _get(target)
            if r.status_code in (401, 403):
                return {"ok": False, "text": "", "reason": "blocked", "stage": "fetch"}
            if r.status_code == 404:
                return {"ok": False, "text": "", "reason": "removed", "stage": "fetch"}
            r.raise_for_status()
            html = r.text or ""
            break
        except Exception:
            html = ""
    if not html:
        return {"ok": False, "text": "", "reason": "fetch_error", "stage": "fetch"}
    if _paywalled(html):
        return {"ok": False, "text": "", "reason": "paywall", "stage": "paywall-check"}
    text = (trafilatura.extract(html) or "").strip()
    if len(text) >= MIN_CHARS:
        return {"ok": True, "text": text, "reason": "", "stage": "trafilatura"}
    try:
        from readability import Document
        text2 = _clean(Document(html).summary())
        if len(text2) >= MIN_CHARS:
            return {"ok": True, "text": text2, "reason": "", "stage": "readability"}
    except Exception:
        text2 = ""
    raw = _clean(html)
    if len(raw) >= MIN_CHARS:
        return {"ok": True, "text": raw, "reason": "", "stage": "raw"}
    return {"ok": False, "text": "", "reason": "thin", "stage": "raw"}
