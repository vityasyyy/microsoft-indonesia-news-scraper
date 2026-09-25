import csv
from unittest.mock import patch
from src import make_corpus

def test_slugify_rules():
    assert make_corpus.slugify("Kompas.com", "unknown") == "kompas-com"
    assert make_corpus.slugify("  ", "unknown") == "unknown"
    assert len(make_corpus.slugify("x" * 100, "a")) == 60

def test_process_row_ok_path_translates_en(tmp_path):
    row = {"No": 7, "Publisher": "DCD", "Title": "Cloud region launched in Indonesia", "URL": "https://x.com/7", "Date": "2025-06-01", "Keyword_Found": "k3"}
    with patch("src.make_corpus.downloader.fetch", return_value={"ok": True, "text": "Microsoft launched its first cloud region in Indonesia", "reason": "", "stage": "trafilatura"}):
        with patch("src.make_corpus.translator.detect_lang", return_value="en"):
            with patch("src.make_corpus.translator.translate_long_en_to_id", return_value=("TERJEMAHAN", True)):
                res = make_corpus.process_row(row, str(tmp_path))
    assert res["status"] == "ok"
    assert res["file"].startswith("007_")
    assert res["file"].endswith(".docx")

def test_process_row_failed_fetch_logged(tmp_path):
    row = {"No": 8, "Publisher": "K", "Title": "T", "URL": "https://x.com/8", "Date": "2025-06-01", "Keyword_Found": "k1"}
    with patch("src.make_corpus.downloader.fetch", return_value={"ok": False, "text": "", "reason": "paywall", "stage": "paywall-check"}):
        res = make_corpus.process_row(row, str(tmp_path))
    assert res["status"] == "failed"
    assert res["reason"] == "paywall"
