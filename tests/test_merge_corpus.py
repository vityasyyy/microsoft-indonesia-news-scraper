import csv
import json

import openpyxl
import pytest

from src import docx_builder, exporter, merge_corpus, schema
from src.merge_corpus import MergeError


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


def write_batch(directory, index, count, results, sha="batch-sha"):
    directory.mkdir(parents=True, exist_ok=True)
    for result in results:
        if result["status"] == "ok":
            docx_builder.build(
                str(directory / result["file"]),
                "Judul",
                {"Language": "id", "Resolved_URL": result.get("Resolved_URL", "")},
                "Body Microsoft",
            )
    failed = [result for result in results if result["status"] != "ok"]
    with open(directory / "failed.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=schema.FAILED_COLUMNS)
        writer.writeheader()
        for result in failed:
            writer.writerow(
                {
                    "No": result["No"],
                    "URL": result["URL"],
                    "Resolved_URL": result.get("Resolved_URL", ""),
                    "Publisher": result["Publisher"],
                    "Keyword_Found": result["Keyword_Found"],
                    "reason": result["reason"],
                    "stage": result.get("stage", ""),
                }
            )
    meta = {
        "run_utc": "2026-11-11T00:00:00+00:00",
        "xlsx": "output/articles-2025.xlsx",
        "input_sha256": sha,
        "rows": len(results),
        "ok": sum(1 for result in results if result["status"] == "ok"),
        "failed": len(failed),
        "by_reason": {result["reason"]: 1 for result in failed},
        "batch_index": index,
        "batch_count": count,
        "workers": 4,
        "results": results,
    }
    (directory / "corpus-meta.json").write_text(json.dumps(meta), encoding="utf-8")


def result(number, status="ok", **over):
    base = {
        "No": number,
        "status": status,
        "URL": f"https://news.google.com/rss/articles/{number}",
        "Resolved_URL": f"https://publisher.com/{number}",
        "Publisher": "Kompas",
        "Keyword_Found": "k1",
        "file": f"{number:03d}_kompas_judul.docx" if status == "ok" else None,
        "reason": None if status == "ok" else "paywall",
        "stage": None if status == "ok" else "extract",
    }
    base.update(over)
    return base


def test_merge_combines_docx_failed_csv_meta_and_updates_xlsx(tmp_path):
    xlsx = tmp_path / "output" / "articles-2025.xlsx"
    write_xlsx(xlsx, count=3)
    batch0 = tmp_path / "corpus-batch-0"
    batch1 = tmp_path / "corpus-batch-1"
    write_batch(batch0, 0, 2, [result(1), result(2, status="failed", reason="paywall")])
    write_batch(batch1, 1, 2, [result(3, Resolved_URL="https://publisher.com/three")])
    out = tmp_path / "corpus"
    (out / "stale.docx").parent.mkdir(parents=True)
    (out / "stale.docx").write_bytes(b"old")

    meta = merge_corpus.merge([str(batch0), str(batch1)], str(out), str(xlsx), expected_batches=2)

    assert meta["rows"] == 3
    assert meta["ok"] == 2
    assert meta["failed"] == 1
    assert meta["batch_count"] == 2
    assert meta["input_sha256"] == merge_corpus.sha256_file(str(xlsx))
    assert not (out / "stale.docx").exists()
    assert sorted(path.name for path in out.glob("*.docx")) == [
        "001_kompas_judul.docx",
        "003_kompas_judul.docx",
    ]
    with open(out / "failed.csv", newline="", encoding="utf-8") as handle:
        failed = list(csv.DictReader(handle))
    assert len(failed) == 1
    assert failed[0]["Resolved_URL"] == "https://publisher.com/2"
    ws = openpyxl.load_workbook(xlsx).active
    statuses = [
        row[schema.COLUMNS.index("Fulltext_Status")] for row in ws.iter_rows(min_row=2, values_only=True)
    ]
    files = [
        row[schema.COLUMNS.index("Docx_File")] for row in ws.iter_rows(min_row=2, values_only=True)
    ]
    assert statuses == ["ok", "paywall", "ok"]
    assert files == ["001_kompas_judul.docx", None, "003_kompas_judul.docx"]


def test_merge_rejects_missing_batch_meta(tmp_path):
    with pytest.raises(MergeError):
        merge_corpus.merge([str(tmp_path / "missing")], str(tmp_path / "out"), str(tmp_path / "x.xlsx"))


def test_merge_rejects_missing_index(tmp_path):
    xlsx = tmp_path / "articles.xlsx"
    write_xlsx(xlsx, count=2)
    write_batch(tmp_path / "b0", 0, 2, [result(1)])
    write_batch(tmp_path / "b2", 2, 2, [result(2)])
    with pytest.raises(MergeError):
        merge_corpus.merge(
            [str(tmp_path / "b0"), str(tmp_path / "b2")],
            str(tmp_path / "out"),
            str(xlsx),
            expected_batches=2,
        )


def test_merge_rejects_expected_batch_count_mismatch(tmp_path):
    xlsx = tmp_path / "articles.xlsx"
    write_xlsx(xlsx, count=1)
    write_batch(tmp_path / "b0", 0, 2, [result(1)])
    with pytest.raises(MergeError):
        merge_corpus.merge(
            [str(tmp_path / "b0")], str(tmp_path / "out"), str(xlsx), expected_batches=2
        )


def test_merge_rejects_mismatched_batch_inputs(tmp_path):
    xlsx = tmp_path / "articles.xlsx"
    write_xlsx(xlsx, count=2)
    write_batch(tmp_path / "b0", 0, 2, [result(1)], sha="first")
    write_batch(tmp_path / "b1", 1, 2, [result(2)], sha="second")
    with pytest.raises(MergeError, match="input_sha256"):
        merge_corpus.merge(
            [str(tmp_path / "b0"), str(tmp_path / "b1")],
            str(tmp_path / "out"),
            str(xlsx),
            expected_batches=2,
        )
