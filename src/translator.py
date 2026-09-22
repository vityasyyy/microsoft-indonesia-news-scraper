"""Detect id/en, translate EN title+snippet to ID, always keep originals."""
from langdetect import detect, LangDetectException

def detect_lang(text):
    t = (text or "").strip()
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

def translate_en_to_id(text):
    t = (text or "").strip()
    if not t:
        return "", True
    try:
        from deep_translator import GoogleTranslator
        out = GoogleTranslator(source="en", target="id").translate(t)
        return (out or t), True
    except Exception:
        return t, False

def enrich(rows):
    out = []
    translated = 0
    failed = 0
    for r in rows:
        lang = detect_lang(r.get("title", "") + " " + r.get("snippet", ""))
        if lang not in ("id", "en"):
            lang = "id" if r.get("locale", "").startswith("id") else lang
        nr = dict(r)
        nr["Title_Original"] = r.get("title", "")
        nr["Snippet_Original"] = r.get("snippet", "")
        nr["Source_Lang"] = lang if lang in ("id", "en") else "unknown"
        if lang == "en":
            ti, ok1 = translate_en_to_id(r.get("title", ""))
            si, ok2 = translate_en_to_id(r.get("snippet", ""))
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
