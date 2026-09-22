"""Date filter (strict 2025) + URL dedupe."""
import re
import urllib.parse
from datetime import date
from dateutil import parser as dateparser

START = date(2025, 1, 1)
END = date(2025, 12, 31)
TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid", "hl", "gl", "ceid"}

def parse_date(raw):
    if not raw:
        return None
    try:
        return dateparser.parse(raw)
    except Exception:
        return None

def is_in_2025(dt):
    if dt is None:
        return False
    d = dt.date() if hasattr(dt, "date") else dt
    return START <= d <= END

def normalize_url(url):
    u = (url or "").strip()
    if not u:
        return ""
    p = urllib.parse.urlparse(u)
    host = (p.hostname or "").lower()
    if host.startswith("news.google.com"):
        return u.strip().rstrip("/")
    qs = urllib.parse.parse_qsl(p.query, keep_blank_values=True)
    qs = [(k, v) for k, v in qs if k not in TRACKING]
    query = urllib.parse.urlencode(qs)
    path = re.sub(r"/+$", "", p.path or "")
    norm = urllib.parse.urlunparse((p.scheme.lower(), host, path, "", query, ""))
    return norm.rstrip("/")

def dedupe(rows):
    seen = {}
    dropped_not_2025 = 0
    dropped_bad_date = 0
    duplicates = 0
    for r in rows:
        dt = parse_date(r.get("published_raw", ""))
        if dt is None:
            dropped_bad_date += 1
            continue
        if not is_in_2025(dt):
            dropped_not_2025 += 1
            continue
        key = normalize_url(r.get("url", "")) or (r.get("title", "") + dt.isoformat())
        if key in seen:
            duplicates += 1
            prev = seen[key]
            extra = r.get("keyword", "")
            if extra and extra not in (prev.get("Keyword_Found", "") + prev.get("Also_Found_In", "")):
                prev["Also_Found_In"] = (prev.get("Also_Found_In", "") + "," + extra).strip(",")
            continue
        nr = dict(r)
        nr["date_iso"] = dt.date().isoformat()
        nr["Keyword_Found"] = r.get("keyword", "")
        nr["Also_Found_In"] = ""
        seen[key] = nr
    kept = list(seen.values())
    return kept, {"fetched": len(rows), "kept": len(kept), "dropped_not_2025": dropped_not_2025, "dropped_bad_date": dropped_bad_date, "duplicates": duplicates}
