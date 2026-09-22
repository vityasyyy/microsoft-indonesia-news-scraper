from src import translator

def test_detect_and_passthrough_id():
    assert translator.detect_lang("Kerja sama Microsoft dengan pemerintah Indonesia") == "id"

def test_enrich_keeps_original_and_marks_ok():
    rows = [{"title": "Kerja sama Microsoft", "snippet": "Ringkasan", "publisher": "Kompas", "url": "https://x.com/1", "date_iso": "2025-03-10", "Keyword_Found": "k1", "Also_Found_In": ""}]
    out, stats = translator.enrich(rows)
    assert out[0]["Title_Original"] == "Kerja sama Microsoft"
    assert out[0]["Title_ID"] == "Kerja sama Microsoft"
    assert out[0]["translation_ok"] in (True, "TRUE", "source=id")
