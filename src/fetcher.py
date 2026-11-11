"""Fetch Google News RSS per query x two-month window x locale."""
import time
import urllib.parse
import urllib.request

import feedparser

LOCALES = (("id", "ID", "ID:id"), ("en-US", "US", "US:en"))
RSS_CAP = 100


def _get(url, timeout=20):
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (news-corpus-research)"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")

    class Result:
        text = body
        status_code = 200

        def raise_for_status(self):
            pass

    return Result()


def build_query(keyword, window):
    start, end = window
    return f"{keyword} after:{start} before:{end}"


def build_url(query, hl, gl, ceid):
    return (
        "https://news.google.com/rss/search?q="
        + urllib.parse.quote(query)
        + f"&hl={hl}&gl={gl}&ceid={ceid}"
    )


def _source(entry):
    source = entry.get("source") or {}
    if hasattr(source, "get"):
        title = (source.get("title") or "").strip()
        href = (source.get("href") or "").strip()
    else:
        title, href = str(source).strip(), ""
    host = (urllib.parse.urlparse(href).hostname or "").lower()
    return title, host


def fetch_window(group, keyword, window, hl, gl, ceid, retries=3):
    query = build_query(keyword, window)
    url = build_url(query, hl, gl, ceid)
    label = f"{keyword!r} {window[0]}..{window[1]} {hl}/{gl}"
    last_error = None
    for attempt in range(retries):
        try:
            response = _get(url)
            response.raise_for_status()
            feed = feedparser.parse(response.text)
            window_label = f"{window[0]}..{window[1]}"
            locale = f"{hl}/{gl}"
            rows = []
            for entry in feed.entries:
                publisher, domain = _source(entry)
                rows.append(
                    {
                        "title": (entry.get("title") or "").strip(),
                        "url": (entry.get("link") or "").strip(),
                        "publisher": publisher,
                        "publisher_domain": domain,
                        "published_raw": entry.get("published") or entry.get("pubDate") or "",
                        "snippet": entry.get("description") or entry.get("summary") or "",
                        "keyword": keyword,
                        "query_group": group,
                        "window": window_label,
                        "locale": locale,
                    }
                )
            return rows
        except Exception as error:  # one window retries; fetch_all isolates windows
            last_error = error
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"fetch failed for {label}: {last_error}")


def fetch_all(queries, windows, locales=LOCALES, delay_s=0.5):
    """Fetch every query/window/locale. Never abort on one window failure."""
    rows = []
    report = {"queries": [], "warnings": []}
    for group, keyword in queries:
        for window in windows:
            for hl, gl, ceid in locales:
                entry = {
                    "group": group,
                    "keyword": keyword,
                    "window": f"{window[0]}..{window[1]}",
                    "locale": f"{hl}/{gl}",
                    "raw": 0,
                    "capped": False,
                    "error": "",
                }
                try:
                    fetched = fetch_window(group, keyword, window, hl, gl, ceid)
                    entry["raw"] = len(fetched)
                    rows.extend(fetched)
                    if len(fetched) >= RSS_CAP:
                        entry["capped"] = True
                        report["warnings"].append(
                            f"RSS cap {RSS_CAP} reached for {keyword!r} "
                            f"{entry['window']} {entry['locale']}; window may be truncated"
                        )
                except Exception as error:
                    entry["error"] = str(error)
                report["queries"].append(entry)
                time.sleep(delay_s)
    return rows, report
