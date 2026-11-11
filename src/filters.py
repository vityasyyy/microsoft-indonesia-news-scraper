"""Date filter, Microsoft relevance gate, government classification, dedupe."""
import re
import urllib.parse
from datetime import date

from dateutil import parser as dateparser

from src.language import clean_html, detect_lang

START = date(2025, 1, 1)
END = date(2025, 12, 31)

# Query params that never change the article identity, on any host.
TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gclid", "fbclid"}

MICROSOFT_SIGNALS = (
    "microsoft",
    "azure",
    "microsoft 365",
    "office 365",
    "copilot",
    "linkedin",
    "github",
    "elevaiate",
    "elevate",
)

GOVERNMENT_ALIASES = (
    ("Komdigi", ("komdigi", "kominfo", "kementerian komunikasi dan digital")),
    ("Kemenag", ("kemenag", "kementerian agama")),
    ("Kemenkeu", ("kemenkeu", "kementerian keuangan")),
    ("Kemenko", ("kemenko", "kementerian koordinator")),
    ("Kementerian Investasi/BKPM", ("kementerian investasi", "bkpm")),
    ("Kemendikbud", ("kemendikbud", "kemendikdasmen", "kementerian pendidikan")),
    ("Kemenkes", ("kemenkes", "kementerian kesehatan")),
    ("Kemendag", ("kemendag", "kementerian perdagangan")),
    ("Bappenas", ("bappenas",)),
    ("BPS", ("bps", "badan pusat statistik")),
    ("Setkab", ("setkab", "sekretariat kabinet")),
    ("Pemprov", ("pemprov", "pemerintah provinsi")),
    ("Pemkot", ("pemkot", "pemerintah kota")),
    ("Pemkab", ("pemkab", "pemerintah kabupaten")),
    ("Dinas", ("dinas",)),
    ("Badan", ("badan",)),
    ("Lembaga", ("lembaga",)),
)

GOVERNMENT_PATTERNS = tuple(
    (label, tuple(re.compile(r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])") for alias in aliases))
    for label, aliases in GOVERNMENT_ALIASES
)


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
    day = dt.date() if hasattr(dt, "date") else dt
    return START <= day <= END


def normalize_url(url):
    """Stable dedupe key: no query for Google News, sorted params elsewhere."""
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urllib.parse.urlparse(raw)
    host = (parsed.hostname or "").lower()
    if not host:
        return raw
    scheme = (parsed.scheme or "https").lower()
    path = re.sub(r"/+$", "", parsed.path or "")
    if host.startswith("news.google."):
        return urllib.parse.urlunparse((scheme, host, path, "", "", ""))
    pairs = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING
    ]
    pairs.sort()
    query = urllib.parse.urlencode(pairs)
    return urllib.parse.urlunparse((scheme, host, path, "", query, "")).rstrip("/")


def has_microsoft_signal(text):
    haystack = clean_html(text).lower()
    return any(signal in haystack for signal in MICROSOFT_SIGNALS)


def source_type(domain):
    host = (domain or "").lower().strip().strip(".")
    return "government" if host == "go.id" or host.endswith(".go.id") else "other"


def government_body(*texts):
    haystack = " ".join(text for text in texts if text).lower()
    if not haystack:
        return ""
    for label, patterns in GOVERNMENT_PATTERNS:
        if any(pattern.search(haystack) for pattern in patterns):
            return label
    return ""


def _merge_duplicate(previous, row):
    keyword = row.get("keyword", "")
    if keyword and keyword != previous["Keyword_Found"] and keyword not in previous["Also_Found_In"]:
        previous["Also_Found_In"].append(keyword)
    group = row.get("query_group", "")
    if group and group not in previous["Found_In_Groups"]:
        previous["Found_In_Groups"].append(group)
    if not previous["Government_Body"]:
        previous["Government_Body"] = government_body(
            row.get("title", ""), row.get("snippet", ""), row.get("publisher", "")
        )


def process(rows, sample_limit=20):
    """Apply date filter, relevance gate, and dedupe in one pass."""
    seen = {}
    per_query = {}
    samples = []
    totals = {
        "fetched": 0,
        "kept": 0,
        "dropped_not_2025": 0,
        "dropped_bad_date": 0,
        "dropped_irrelevant": 0,
        "duplicates": 0,
    }
    for row in rows:
        key = (row.get("keyword", ""), row.get("window", ""), row.get("locale", ""))
        stats = per_query.setdefault(
            key,
            {
                "group": row.get("query_group", ""),
                "keyword": key[0],
                "window": key[1],
                "locale": key[2],
                "raw": 0,
                "kept": 0,
                "dropped_not_2025": 0,
                "dropped_bad_date": 0,
                "dropped_irrelevant": 0,
                "duplicates": 0,
            },
        )
        stats["raw"] += 1
        totals["fetched"] += 1

        published = parse_date(row.get("published_raw", ""))
        if published is None:
            stats["dropped_bad_date"] += 1
            totals["dropped_bad_date"] += 1
            continue
        if not is_in_2025(published):
            stats["dropped_not_2025"] += 1
            totals["dropped_not_2025"] += 1
            continue

        title = (row.get("title") or "").strip()
        snippet = clean_html(row.get("snippet") or "")
        if not has_microsoft_signal(f"{title} {snippet}"):
            stats["dropped_irrelevant"] += 1
            totals["dropped_irrelevant"] += 1
            if title and len(samples) < sample_limit:
                samples.append(title)
            continue

        day = published.date().isoformat()
        dedupe_key = normalize_url(row.get("url", "")) or f"{title}|{day}"
        if dedupe_key in seen:
            stats["duplicates"] += 1
            totals["duplicates"] += 1
            _merge_duplicate(seen[dedupe_key], row)
            continue

        group = row.get("query_group", "baseline")
        seen[dedupe_key] = {
            "Publisher": row.get("publisher", ""),
            "Publisher_Domain": row.get("publisher_domain", ""),
            "Source_Type": source_type(row.get("publisher_domain", "")),
            "Query_Group": group,
            "Found_In_Groups": [group],
            "Title": title,
            "Snippet": snippet,
            "URL": row.get("url", "").strip(),
            "Date": day,
            "Keyword_Found": row.get("keyword", ""),
            "Also_Found_In": [],
            "Source_Lang": detect_lang(f"{title} {snippet}"),
            "Government_Body": government_body(title, snippet, row.get("publisher", "")),
            "Fulltext_Status": "pending",
            "Docx_File": "",
        }
        stats["kept"] += 1
        totals["kept"] += 1

    totals["per_query"] = list(per_query.values())
    totals["dropped_irrelevant_samples"] = samples
    return list(seen.values()), totals
