import json

import pytest

from src import exporter, release_gate, schema
from src.release_gate import GateError


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
            "Fulltext_Status": "ok",
            "Docx_File": f"{number:03d}.docx",
        }
    )
    row.update(over)
    return row


def write_inputs(tmp_path, rows=None, run_meta=None, corpus_meta=None):
    rows = [xlsx_row(1)] if rows is None else rows
    xlsx = tmp_path / "articles-2025.xlsx"
    exporter.export_xlsx(rows, str(xlsx))
    run_path = tmp_path / "run-meta.json"
    run_path.write_text(
        json.dumps(
            run_meta
            if run_meta is not None
            else {
                "run_utc": "2026-11-11T00:00:00+00:00",
                "queries": [{"keyword": "q", "window": "w", "locale": "id/ID"}],
                "fetch_total": len(rows),
                "kept": len(rows),
                "windows": ["2025-01-01..2025-03-01"],
            }
        ),
        encoding="utf-8",
    )
    corpus_path = tmp_path / "corpus-meta.json"
    corpus_path.write_text(
        json.dumps(
            corpus_meta
            if corpus_meta is not None
            else {
                "run_utc": "2026-11-11T00:00:00+00:00",
                "input_sha256": "abc",
                "rows": len(rows),
                "ok": len(rows),
                "failed": 0,
                "by_reason": {},
                "batch_count": 1,
                "results": [
                    {"No": row["No"], "status": "ok", "file": row["Docx_File"]} for row in rows
                ],
            }
        ),
        encoding="utf-8",
    )
    for row in rows:
        if row["Docx_File"]:
            (tmp_path / row["Docx_File"]).write_bytes(b"docx")
    return str(xlsx), str(run_path), str(corpus_path)


def test_gate_accepts_valid_release(tmp_path):
    paths = write_inputs(tmp_path)
    assert release_gate.check(*paths, expected_batches=1) is True


def test_gate_rejects_zero_rows(tmp_path):
    xlsx = tmp_path / "articles-2025.xlsx"
    exporter.export_xlsx([], str(xlsx))
    run_path = tmp_path / "run-meta.json"
    run_path.write_text(
        json.dumps(
            {
                "run_utc": "x",
                "queries": [],
                "fetch_total": 0,
                "kept": 0,
                "windows": [],
            }
        ),
        encoding="utf-8",
    )
    corpus_path = tmp_path / "corpus-meta.json"
    corpus_path.write_text(
        json.dumps(
            {
                "run_utc": "x",
                "input_sha256": "abc",
                "rows": 0,
                "ok": 0,
                "failed": 0,
                "by_reason": {},
                "batch_count": 1,
                "results": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(GateError, match="zero"):
        release_gate.check(str(xlsx), str(run_path), str(corpus_path), expected_batches=1)


def test_gate_rejects_non_2025_date(tmp_path):
    paths = write_inputs(tmp_path, rows=[xlsx_row(1, Date="2026-01-01")])
    with pytest.raises(GateError, match="2025"):
        release_gate.check(*paths, expected_batches=1)


def test_gate_rejects_duplicate_urls(tmp_path):
    rows = [
        xlsx_row(1, URL="https://x.com/a?utm_source=1"),
        xlsx_row(2, URL="https://x.com/a"),
    ]
    paths = write_inputs(tmp_path, rows=rows)
    with pytest.raises(GateError, match="duplicate"):
        release_gate.check(*paths, expected_batches=1)


def test_gate_rejects_missing_required_meta(tmp_path):
    corpus_meta = {
        "run_utc": "x",
        "rows": 1,
        "ok": 1,
        "failed": 0,
        "by_reason": {},
        "batch_count": 1,
        "results": [],
    }
    paths = write_inputs(tmp_path, corpus_meta=corpus_meta)
    with pytest.raises(GateError, match="input_sha256"):
        release_gate.check(*paths, expected_batches=1)


def test_gate_rejects_missing_batch(tmp_path):
    paths = write_inputs(tmp_path)
    with pytest.raises(GateError, match="batch"):
        release_gate.check(*paths, expected_batches=3)


def test_gate_rejects_row_count_mismatch(tmp_path):
    corpus_meta = {
        "run_utc": "x",
        "input_sha256": "abc",
        "rows": 2,
        "ok": 2,
        "failed": 0,
        "by_reason": {},
        "batch_count": 1,
        "results": [{"No": 1, "status": "ok"}, {"No": 2, "status": "ok"}],
    }
    paths = write_inputs(tmp_path, corpus_meta=corpus_meta)
    with pytest.raises(GateError, match="rows"):
        release_gate.check(*paths, expected_batches=1)


def test_gate_rejects_incomplete_row_coverage(tmp_path):
    corpus_meta = {
        "run_utc": "x",
        "input_sha256": "abc",
        "rows": 1,
        "ok": 1,
        "failed": 0,
        "by_reason": {},
        "batch_count": 1,
        "results": [{"No": 2, "status": "ok", "file": "x.docx"}],
    }
    paths = write_inputs(tmp_path, corpus_meta=corpus_meta)
    with pytest.raises(GateError, match="cover"):
        release_gate.check(*paths, expected_batches=1)


def test_gate_rejects_invalid_failure_reason(tmp_path):
    corpus_meta = {
        "run_utc": "x",
        "input_sha256": "abc",
        "rows": 1,
        "ok": 0,
        "failed": 1,
        "by_reason": {"weird": 1},
        "batch_count": 1,
        "results": [{"No": 1, "status": "failed", "reason": "weird"}],
    }
    paths = write_inputs(tmp_path, corpus_meta=corpus_meta)
    with pytest.raises(GateError, match="status/reason"):
        release_gate.check(*paths, expected_batches=1)


def test_gate_rejects_pending_fulltext_status(tmp_path):
    rows = [xlsx_row(1, Fulltext_Status="pending", Docx_File="")]
    paths = write_inputs(tmp_path, rows=rows)
    with pytest.raises(GateError, match="pending"):
        release_gate.check(*paths, expected_batches=1)


def test_gate_rejects_ok_row_without_docx_file(tmp_path):
    rows = [xlsx_row(1, Docx_File="")]
    corpus_meta = {
        "run_utc": "x",
        "input_sha256": "abc",
        "rows": 1,
        "ok": 1,
        "failed": 0,
        "by_reason": {},
        "batch_count": 1,
        "results": [{"No": 1, "status": "ok", "file": "001.docx"}],
    }
    paths = write_inputs(tmp_path, rows=rows, corpus_meta=corpus_meta)
    (tmp_path / "001.docx").write_bytes(b"docx")
    with pytest.raises(GateError, match="Docx_File"):
        release_gate.check(*paths, expected_batches=1)


def test_gate_rejects_missing_docx_file(tmp_path):
    paths = write_inputs(tmp_path)
    (tmp_path / "001.docx").unlink()
    with pytest.raises(GateError, match="missing"):
        release_gate.check(*paths, expected_batches=1)


def test_gate_rejects_docx_file_on_failed_row(tmp_path):
    rows = [xlsx_row(1, Fulltext_Status="paywall", Docx_File="001.docx")]
    paths = write_inputs(tmp_path, rows=rows)
    with pytest.raises(GateError, match="Docx_File"):
        release_gate.check(*paths, expected_batches=1)


def test_gate_rejects_corpus_counts_not_adding_up(tmp_path):
    corpus_meta = {
        "run_utc": "x",
        "input_sha256": "abc",
        "rows": 1,
        "ok": 1,
        "failed": 1,
        "by_reason": {"paywall": 1},
        "batch_count": 1,
        "results": [{"No": 1, "status": "ok", "file": "001.docx"}],
    }
    paths = write_inputs(tmp_path, corpus_meta=corpus_meta)
    with pytest.raises(GateError, match="ok\\+failed"):
        release_gate.check(*paths, expected_batches=1)


def test_gate_rejects_missing_ok_result_file(tmp_path):
    corpus_meta = {
        "run_utc": "x",
        "input_sha256": "abc",
        "rows": 1,
        "ok": 1,
        "failed": 0,
        "by_reason": {},
        "batch_count": 1,
        "results": [{"No": 1, "status": "ok", "file": "999_missing.docx"}],
    }
    paths = write_inputs(tmp_path, corpus_meta=corpus_meta)
    with pytest.raises(GateError, match="missing"):
        release_gate.check(*paths, expected_batches=1)


def test_gate_accepts_ok_and_failed_rows(tmp_path):
    rows = [xlsx_row(1), xlsx_row(2, Fulltext_Status="paywall", Docx_File="")]
    corpus_meta = {
        "run_utc": "x",
        "input_sha256": "abc",
        "rows": 2,
        "ok": 1,
        "failed": 1,
        "by_reason": {"paywall": 1},
        "batch_count": 1,
        "results": [
            {"No": 1, "status": "ok", "file": "001.docx"},
            {"No": 2, "status": "failed", "reason": "paywall"},
        ],
    }
    paths = write_inputs(tmp_path, rows=rows, corpus_meta=corpus_meta)
    assert release_gate.check(*paths, expected_batches=1) is True


def test_gate_rejects_xlsx_ok_but_corpus_failed(tmp_path):
    corpus_meta = {
        "run_utc": "x",
        "input_sha256": "abc",
        "rows": 1,
        "ok": 0,
        "failed": 1,
        "by_reason": {"paywall": 1},
        "batch_count": 1,
        "results": [{"No": 1, "status": "failed", "reason": "paywall"}],
    }
    paths = write_inputs(tmp_path, corpus_meta=corpus_meta)
    with pytest.raises(GateError, match="status mismatch"):
        release_gate.check(*paths, expected_batches=1)


def test_gate_rejects_xlsx_failed_but_corpus_ok(tmp_path):
    rows = [xlsx_row(1, Fulltext_Status="paywall", Docx_File="")]
    corpus_meta = {
        "run_utc": "x",
        "input_sha256": "abc",
        "rows": 1,
        "ok": 1,
        "failed": 0,
        "by_reason": {},
        "batch_count": 1,
        "results": [{"No": 1, "status": "ok", "file": "001.docx"}],
    }
    paths = write_inputs(tmp_path, rows=rows, corpus_meta=corpus_meta)
    (tmp_path / "001.docx").write_bytes(b"docx")
    with pytest.raises(GateError, match="status mismatch"):
        release_gate.check(*paths, expected_batches=1)


def test_gate_rejects_docx_file_mismatch(tmp_path):
    corpus_meta = {
        "run_utc": "x",
        "input_sha256": "abc",
        "rows": 1,
        "ok": 1,
        "failed": 0,
        "by_reason": {},
        "batch_count": 1,
        "results": [{"No": 1, "status": "ok", "file": "002.docx"}],
    }
    paths = write_inputs(tmp_path, corpus_meta=corpus_meta)
    (tmp_path / "002.docx").write_bytes(b"docx")
    with pytest.raises(GateError, match="Docx_File mismatch"):
        release_gate.check(*paths, expected_batches=1)


def test_gate_rejects_orphan_corpus_docx(tmp_path):
    paths = write_inputs(tmp_path)
    (tmp_path / "orphan.docx").write_bytes(b"docx")
    with pytest.raises(GateError, match="docx"):
        release_gate.check(*paths, expected_batches=1)


def test_gate_rejects_empty_url(tmp_path):
    rows = [xlsx_row(1, URL="")]
    paths = write_inputs(tmp_path, rows=rows)
    with pytest.raises(GateError, match="URL"):
        release_gate.check(*paths, expected_batches=1)


def test_gate_rejects_invalid_iso_date(tmp_path):
    rows = [xlsx_row(1, Date="2025-99-99")]
    paths = write_inputs(tmp_path, rows=rows)
    with pytest.raises(GateError, match="date"):
        release_gate.check(*paths, expected_batches=1)
