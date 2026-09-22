"""Fetch Google News RSS per keyword x locale."""
import time
import urllib.parse
import feedparser

LOCALES = [("id", "ID", "ID:id"), ("en-US", "US", "US:en")]

def _get(url, timeout=20):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (skripsi-research)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8", errors="replace")
    class R:
        text = body
        status_code = 200
        def raise_for_status(self): pass
    return R()

def fetch_keyword_rss(keyword, hl, gl, ceid, retries=3):
    q = urllib.parse.quote(keyword)
    url = f"https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={ceid}"
    last = None
    for attempt in range(retries):
        try:
            resp = _get(url)
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
            rows = []
            for e in feed.entries:
                rows.append({
                    "title": e.get("title", "").strip(),
                    "url": e.get("link", "").strip(),
                    "publisher": (e.get("source", {}) or {}).get("title", "").strip() if isinstance(e.get("source"), dict) else str(e.get("source", "")).strip(),
                    "published_raw": e.get("published", "") or e.get("pubDate", ""),
                    "snippet": e.get("description", "") or e.get("summary", ""),
                    "keyword": keyword,
                    "locale": f"{hl}/{gl}",
                })
            return rows
        except Exception as ex:
            last = ex
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"fetch failed for {keyword!r} {hl}/{gl}: {last}")

def fetch_all(keywords, delay_s=2):
    all_rows = []
    for kw in keywords:
        for (hl, gl, ceid) in LOCALES:
            all_rows.extend(fetch_keyword_rss(kw, hl, gl, ceid))
            time.sleep(delay_s)
    return all_rows
