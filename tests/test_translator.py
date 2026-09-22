from unittest.mock import patch
from src import translator

def test_detect_and_passthrough_id():
    assert translator.detect_lang("Kerja sama Microsoft dengan pemerintah Indonesia") == "id"

def test_enrich_keeps_original_and_marks_ok():
    rows = [{"title": "Kerja sama Microsoft", "snippet": "Ringkasan", "publisher": "Kompas", "url": "https://x.com/1", "date_iso": "2025-03-10", "Keyword_Found": "k1", "Also_Found_In": ""}]
    out, stats = translator.enrich(rows)
    assert out[0]["Title_Original"] == "Kerja sama Microsoft"
    assert out[0]["Title_ID"] == "Kerja sama Microsoft"
    assert out[0]["translation_ok"] in (True, "TRUE", "source=id")

def test_id_title_with_english_brand_words_not_translated():
    title = "Microsoft Resmikan Cloud Region Pertamanya di Indonesia Untuk Dorong Ekonomi Berbasis AI"
    snippet = '<a href="https://news.google.com/rss/articles/CBMiiAFBVV95?oc=5" target="_blank">Microsoft Resmikan Cloud Region Pertamanya di Indonesia</a>'
    rows = [{"title": title, "snippet": snippet, "publisher": "Microsoft", "url": "https://x.com/2", "date_iso": "2025-05-27", "Keyword_Found": "k3", "Also_Found_In": "", "locale": "id/ID"}]
    with patch("src.translator.translate_en_to_id", side_effect=AssertionError("must not translate id rows")):
        out, _ = translator.enrich(rows)
    assert out[0]["Source_Lang"] == "id"
    assert out[0]["Title_ID"] == title
    assert out[0]["translation_ok"] is True
    assert "<a" not in out[0]["Snippet_Original"]

def test_true_english_text_stays_english():
    rows = [{"title": "Microsoft launched its first cloud region in Indonesia to boost the AI economy", "snippet": "", "publisher": "DCD", "url": "https://x.com/3", "date_iso": "2025-05-27", "Keyword_Found": "k3", "Also_Found_In": "", "locale": "id/ID"}]
    with patch("src.translator.translate_en_to_id", return_value=("TERJEMAHAN", True)):
        out, _ = translator.enrich(rows)
    assert out[0]["Source_Lang"] == "en"
    assert out[0]["Title_ID"] == "TERJEMAHAN"

def test_translate_retries_transient_backend_error():
    calls = {"n": 0}
    class FakeTranslation:
        def translate(self, text):
            calls["n"] += 1
            return "Hasil terjemahan"
    with patch("src.translator._get_translation", side_effect=[RuntimeError("backend busy"), FakeTranslation()]):
        with patch("time.sleep", return_value=None):
            out, ok = translator.translate_en_to_id("Some english headline here")
    assert ok is True
    assert out == "Hasil terjemahan"
    assert calls["n"] == 1
