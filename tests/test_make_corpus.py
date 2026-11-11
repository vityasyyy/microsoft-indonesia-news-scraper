import hashlib
import json

import openpyxl
import pytest
from docx import Document
from openpyxl import Workbook

from src import docx_builder, exporter, make_corpus, schema


def xlsx_row(number, **over):
    row = {column: "" for column in schema.COLUMNS}
    row.update(
        {
            "No": number,
            "Publisher": "Kompas",
            "Publisher_Domain": "kompas.com",
            "Source_Type": "other",
            "Query_Group": "baseline",
            "Found_In_Groups": "baseline",
            "Title": f"Microsoft artikel {number}",
            "Snippet": "Azure",
            "URL": f"https://x.com/{number}",
            "Date": "2025-03-10",
            "Keyword_Found": "k1",
            "Source_Lang": "id",
            "Fulltext_Status": "pending",
        }
    )
    row.update(over)
    return row


def write_xlsx(path, count=3):
    path.parent.mkdir(parents=True, exist_ok=True)
    exporter.export_xlsx([xlsx_row(number + 1) for number in range(count)], str(path))


def test_slugify_rules():
    assert make_corpus.slugify("Kompas.com", "unknown") == "kompas-com"
    assert make_corpus.slugify("  ", "unknown") == "unknown"
    assert len(make_corpus.slugify("x" * 100, "a")) == 60


def test_read_rows_uses_schema_v2(tmp_path):
    path = tmp_path / "articles.xlsx"
    write_xlsx(path, count=2)
    rows = make_corpus.read_rows(str(path))
    assert [row["No"] for row in rows] == [1, 2]
    assert rows[0]["Title"] == "Microsoft artikel 1"
    assert rows[0]["Publisher"] == "Kompas"
    assert rows[0]["Source_Lang"] == "id"


def test_read_rows_rejects_v1_headers(tmp_path):
    path = tmp_path / "old.xlsx"
    workbook = Workbook()
    ws = workbook.active
    ws.append(["No", "Publisher", "Legacy_Column", "Old_Title"])
    ws.append([1, "Kompas", "Judul", "Title"])
    workbook.save(path)
    with pytest.raises(schema.SchemaError):
        make_corpus.read_rows(str(path))


def test_batch_rows_is_deterministic_slice():
    rows = [{"No": number} for number in range(1, 6)]
    assert [row["No"] for row in make_corpus.batch_rows(rows, 0, 2)] == [1, 3, 5]
    assert [row["No"] for row in make_corpus.batch_rows(rows, 1, 2)] == [2, 4]


def test_batch_rows_validates_index_and_count():
    with pytest.raises(ValueError):
        make_corpus.batch_rows([], 2, 2)
    with pytest.raises(ValueError):
        make_corpus.batch_rows([], 0, 0)


def test_resolve_outdir_preview_batch_full():
    assert make_corpus.resolve_outdir(0, 1, 0, False) == "corpus"
    assert make_corpus.resolve_outdir(5, 1, 0, False) == "corpus-preview"
    assert make_corpus.resolve_outdir(0, 1, 0, True) == "corpus-preview"
    assert make_corpus.resolve_outdir(0, 3, 1, False) == "corpus-batch-1"


def test_config_from_env_defaults_and_batch_validation():
    config = make_corpus.config_from_env({})
    assert config["batch_count"] == 1
    assert config["batch_index"] == 0
    assert config["out_dir"] == "corpus"
    assert config["update_xlsx"] is True
    batch = make_corpus.config_from_env(
        {"BATCH_COUNT": "3", "BATCH_INDEX": "1", "CORPUS_WORKERS": "4"}
    )
    assert batch["out_dir"] == "corpus-batch-1"
    assert batch["workers"] == 4
    assert batch["update_xlsx"] is False
    with pytest.raises(ValueError):
        make_corpus.config_from_env({"BATCH_COUNT": "2", "BATCH_INDEX": "2"})
    with pytest.raises(ValueError):
        make_corpus.config_from_env({"BATCH_COUNT": "0"})


def test_clear_stale_docx(tmp_path):
    (tmp_path / "old.docx").write_bytes(b"x")
    (tmp_path / "keep.csv").write_text("x", encoding="utf-8")
    make_corpus.clear_stale_docx(tmp_path)
    assert not (tmp_path / "old.docx").exists()
    assert (tmp_path / "keep.csv").exists()


def test_process_row_ok_writes_original_body_and_language_metadata(tmp_path):
    row = {
        "No": 7,
        "Publisher": "DCD",
        "Title": "Cloud region launched in Indonesia",
        "URL": "https://news.google.com/rss/articles/abc",
        "Date": "2025-06-01",
        "Keyword_Found": "k3",
    }
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            make_corpus.downloader,
            "fetch",
            lambda url: {
                "ok": True,
                "text": "Microsoft launched its first cloud region in Indonesia",
                "reason": "",
                "stage": "trafilatura",
                "resolved_url": "https://dcd.com/article",
            },
        )
        result = make_corpus.process_row(row, str(tmp_path), accessed="2026-11-11")
    assert result["status"] == "ok"
    assert result["file"].startswith("007_")
    assert result["file"].endswith(".docx")
    doc = Document(str(tmp_path / result["file"]))
    texts = [paragraph.text for paragraph in doc.paragraphs]
    assert any("Language: en" in text for text in texts)
    assert any("Resolved URL: https://dcd.com/article" in text for text in texts)
    assert any("Microsoft launched" in text for text in texts)


def test_row_language_prefers_indonesian_title_over_english_boilerplate():
    title = "Microsoft Resmikan Pusat Data Baru di Indonesia"
    body = "This article was originally published by the editorial team. " * 40
    assert make_corpus.row_language(title, body) == "id"


def test_row_language_uses_indonesian_body_for_english_title():
    title = "Microsoft launches new cloud region in Indonesia"
    body = "Microsoft resmi meluncurkan pusat data pertama di Indonesia pada tahun ini. " * 40
    assert make_corpus.row_language(title, body) == "id"


def test_row_language_stays_unknown_without_signal():
    assert make_corpus.row_language("AI", "ok") == "unknown"


def test_row_language_falls_back_to_xlsx_source_lang():
    title, body = "12345 67890 abc", "12345 67890 abc" * 20
    assert make_corpus.row_language(title, body, "id") == "id"


def test_row_language_uses_other_only_when_all_signals_disagree_with_id_en():
    title, body = "12345 67890 abc", "12345 67890 abc" * 20
    assert make_corpus.row_language(title, body, "other") == "other"
    assert make_corpus.row_language(title, body) == "unknown"


def test_process_row_labels_indonesian_article_despite_english_boilerplate(tmp_path):
    row = {
        "No": 10,
        "Publisher": "K",
        "Title": "Microsoft Resmikan Pusat Data Baru di Indonesia",
        "URL": "https://x.com/10",
        "Date": "2025-06-01",
        "Keyword_Found": "k1",
        "Source_Lang": "other",
    }
    body = "This article was originally published by the editorial team. " * 40
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            make_corpus.downloader,
            "fetch",
            lambda url: {
                "ok": True,
                "text": body,
                "reason": "",
                "stage": "trafilatura",
                "resolved_url": "https://x.com/10",
            },
        )
        result = make_corpus.process_row(row, str(tmp_path), accessed="2026-11-11")
    assert result["language"] == "id"
    doc = Document(str(tmp_path / result["file"]))
    assert any("Language: id" in paragraph.text for paragraph in doc.paragraphs)


def test_process_row_failed_fetch_carries_resolved_url(tmp_path):
    row = {
        "No": 8,
        "Publisher": "K",
        "Title": "Microsoft T",
        "URL": "https://news.google.com/rss/articles/def",
        "Date": "2025-06-01",
        "Keyword_Found": "k1",
    }
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            make_corpus.downloader,
            "fetch",
            lambda url: {
                "ok": False,
                "text": "",
                "reason": "paywall",
                "stage": "extract",
                "resolved_url": "https://k.com/paywalled",
            },
        )
        result = make_corpus.process_row(row, str(tmp_path))
    assert result["status"] == "failed"
    assert result["reason"] == "paywall"
    assert result["Resolved_URL"] == "https://k.com/paywalled"


def test_process_row_docx_error_becomes_internal_error(tmp_path):
    row = {
        "No": 9,
        "Publisher": "K",
        "Title": "Microsoft T",
        "URL": "https://x.com/9",
        "Date": "2025-06-01",
        "Keyword_Found": "k1",
    }
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            make_corpus.downloader,
            "fetch",
            lambda url: {
                "ok": True,
                "text": "Body",
                "reason": "",
                "stage": "trafilatura",
                "resolved_url": "https://x.com/9",
            },
        )
        mp.setattr(make_corpus.docx_builder, "build", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
        result = make_corpus.process_row(row, str(tmp_path))
    assert result["status"] == "failed"
    assert result["reason"] == "internal_error"


def test_safe_process_catches_unexpected_row_errors(tmp_path):
    result = make_corpus.safe_process(
        {"No": "not-a-number", "URL": "https://x.com/x", "Publisher": "K", "Keyword_Found": "k1"},
        str(tmp_path),
    )
    assert result["status"] == "failed"
    assert result["reason"] == "internal_error"


def test_build_meta_includes_input_sha256(tmp_path):
    xlsx = tmp_path / "articles.xlsx"
    xlsx.write_bytes(b"abc")
    config = {
        "xlsx": str(xlsx),
        "batch_index": 0,
        "batch_count": 1,
        "workers": 4,
        "out_dir": "corpus",
        "preview": False,
    }
    results = [{"No": 1, "status": "ok", "file": "001.docx", "Resolved_URL": "https://x.com/1"}]
    meta = make_corpus.build_meta(config, results)
    assert meta["input_sha256"] == hashlib.sha256(b"abc").hexdigest()
    assert meta["rows"] == 1
    assert meta["ok"] == 1
    assert meta["batch_index"] == 0
    assert meta["batch_count"] == 1


def test_preview_run_writes_preview_dir_and_leaves_xlsx_pending(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    xlsx = tmp_path / "output" / "articles-2025.xlsx"
    write_xlsx(xlsx, count=2)
    for name in ("BATCH_COUNT", "BATCH_INDEX", "PREVIEW", "CORPUS_OUT", "CORPUS_XLSX"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LIMIT", "1")
    monkeypatch.setattr(
        make_corpus.downloader,
        "fetch",
        lambda url: {
            "ok": True,
            "text": "Microsoft body text",
            "reason": "",
            "stage": "trafilatura",
            "resolved_url": "https://pub/1",
        },
    )
    assert make_corpus.main() == 0
    preview = tmp_path / "corpus-preview"
    assert preview.is_dir()
    assert not (tmp_path / "corpus").exists()
    meta = json.loads((preview / "corpus-meta.json").read_text(encoding="utf-8"))
    assert meta["rows"] == 1
    assert meta["input_sha256"] == hashlib.sha256(xlsx.read_bytes()).hexdigest()
    ws = openpyxl.load_workbook(xlsx).active
    statuses = [
        row[schema.COLUMNS.index("Fulltext_Status")] for row in ws.iter_rows(min_row=2, values_only=True)
    ]
    assert statuses == ["pending", "pending"]


def test_full_run_clears_stale_docx_and_updates_xlsx(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    xlsx = tmp_path / "output" / "articles-2025.xlsx"
    write_xlsx(xlsx, count=2)
    stale = tmp_path / "corpus" / "stale.docx"
    stale.parent.mkdir()
    stale.write_bytes(b"stale")
    for name in ("BATCH_COUNT", "BATCH_INDEX", "PREVIEW", "CORPUS_OUT", "CORPUS_XLSX", "LIMIT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        make_corpus.downloader,
        "fetch",
        lambda url: {
            "ok": True,
            "text": "Microsoft body text",
            "reason": "",
            "stage": "trafilatura",
            "resolved_url": "https://pub/1",
        },
    )
    assert make_corpus.main() == 0
    assert not stale.exists()
    meta = json.loads((tmp_path / "corpus" / "corpus-meta.json").read_text(encoding="utf-8"))
    assert meta["batch_count"] == 1
    assert meta["ok"] == 2
    ws = openpyxl.load_workbook(xlsx).active
    statuses = [
        row[schema.COLUMNS.index("Fulltext_Status")] for row in ws.iter_rows(min_row=2, values_only=True)
    ]
    assert statuses == ["ok", "ok"]


def test_batch_run_uses_deterministic_slice(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    xlsx = tmp_path / "output" / "articles-2025.xlsx"
    write_xlsx(xlsx, count=5)
    for name in ("LIMIT", "PREVIEW", "CORPUS_OUT", "CORPUS_XLSX"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("BATCH_INDEX", "1")
    monkeypatch.setenv("BATCH_COUNT", "2")
    seen = []

    def fake_fetch(url):
        seen.append(url)
        return {
            "ok": True,
            "text": "Microsoft body text",
            "reason": "",
            "stage": "trafilatura",
            "resolved_url": url,
        }

    monkeypatch.setattr(make_corpus.downloader, "fetch", fake_fetch)
    assert make_corpus.main() == 0
    batch = tmp_path / "corpus-batch-1"
    meta = json.loads((batch / "corpus-meta.json").read_text(encoding="utf-8"))
    assert [result["No"] for result in meta["results"]] == [2, 4]
    assert meta["batch_index"] == 1
    assert meta["batch_count"] == 2
    ws = openpyxl.load_workbook(xlsx).active
    statuses = [
        row[schema.COLUMNS.index("Fulltext_Status")] for row in ws.iter_rows(min_row=2, values_only=True)
    ]
    assert statuses == ["pending"] * 5
