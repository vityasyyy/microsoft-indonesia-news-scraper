"""Label the original article language. No translation, ever."""
import html
import re

from langdetect import DetectorFactory, LangDetectException, detect

DetectorFactory.seed = 0

SCRIPT_RE = re.compile(r"(?is)<(script|style)\b.*?</\1>")
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


def strip_scripts(raw_html):
    """Remove script/style blocks before extraction or text cleaning."""
    return SCRIPT_RE.sub(" ", raw_html or "")


def clean_html(text):
    """Strip tags, scripts, entities, and collapse whitespace."""
    stripped = TAG_RE.sub(" ", strip_scripts(text))
    return WS_RE.sub(" ", html.unescape(stripped)).strip()


def detect_lang(text):
    """Return id/en/other/unknown. Never falls back to the feed locale."""
    cleaned = clean_html(text)
    if len(cleaned) < 12:
        return "unknown"
    try:
        lang = detect(cleaned)
    except LangDetectException:
        return "unknown"
    if lang == "id":
        return "id"
    if lang.startswith("en"):
        return "en"
    return "other"
