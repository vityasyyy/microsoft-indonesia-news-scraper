"""Detect id/en, translate EN title+snippet to ID, always keep originals."""
import re
import time
from langdetect import detect, LangDetectException

TAG_RE = re.compile(r"<[^>]+>")
URL_RE = re.compile(r"https?://\S+")

def clean_text(text):
    """Strip RSS HTML tags/URLs so detection and stored snippets see real words."""
    t = TAG_RE.sub(" ", text or "")
    t = URL_RE.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()

def detect_lang(text):
    t = clean_text(text)
    if len(t) < 12:
        return "unknown"
    try:
        lang = detect(t)
        if lang.startswith("id") or lang == "ms":
            return "id"
        if lang.startswith("en"):
            return "en"
        return lang
    except LangDetectException:
        return "unknown"

_EN_ID = None

def _get_translation():
    """Cached offline EN->ID translation (Argos). Installs the model on first use."""
    global _EN_ID
    if _EN_ID is None:
        from argostranslate import package as _pkg
        from argostranslate import translate as _tr
        try:
            langs = {l.code: l for l in _tr.get_installed_languages()}
            _EN_ID = langs["en"].get_translation(langs["id"])
        except Exception:
            _pkg.update_package_index()
            avail = _pkg.get_available_packages()
            cand = [p for p in avail if p.from_code == "en" and p.to_code == "id"]
            if not cand:
                raise RuntimeError("no offline en->id model available")
            best = sorted(cand, key=lambda p: p.package_version)[-1]
            _pkg.install_from_path(best.download())
            langs = {l.code: l for l in _tr.get_installed_languages()}
            _EN_ID = langs["en"].get_translation(langs["id"])
    return _EN_ID

def translate_en_to_id(text, attempts=3):
    t = (text or "").strip()
    if not t:
        return "", True
    for i in range(attempts):
        try:
            out = _get_translation().translate(t)
            return (out or t), True
        except Exception:
            if i < attempts - 1:
                time.sleep(2 ** i)  # backoff 1s, 2s on transient backend errors
    return t, False

def enrich(rows):
    out = []
    translated = 0
    failed = 0
    for r in rows:
        snippet_clean = clean_text(r.get("snippet", ""))
        lang = detect_lang(r.get("title", "") + " " + snippet_clean)
        if lang not in ("id", "en"):
            lang = "id" if r.get("locale", "").startswith("id") else lang
        nr = dict(r)
        nr["Title_Original"] = r.get("title", "")
        nr["Snippet_Original"] = snippet_clean
        nr["Source_Lang"] = lang if lang in ("id", "en") else "unknown"
        if lang == "en":
            ti, ok1 = translate_en_to_id(r.get("title", ""))
            si, ok2 = translate_en_to_id(snippet_clean)
            nr["Title_ID"] = ti
            nr["Snippet_ID"] = si
            nr["translation_ok"] = bool(ok1 and ok2)
            translated += 1
            if not nr["translation_ok"]:
                failed += 1
        else:
            nr["Title_ID"] = r.get("title", "")
            nr["Snippet_ID"] = r.get("snippet", "")
            nr["translation_ok"] = True
        out.append(nr)
    return out, {"en_translated": translated, "translation_failed": failed}
