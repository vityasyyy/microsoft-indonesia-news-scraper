"""Release gate: refuse to publish an empty, out-of-scope, or incomplete corpus."""
import argparse
import datetime
import json
import pathlib
import sys

import openpyxl

from src.filters import normalize_url
from src.schema import FULLTEXT_STATUSES, validate_headers

FAILURE_REASONS = set(FULLTEXT_STATUSES) - {"pending", "ok"}

REQUIRED_RUN_META = ("run_utc", "queries", "fetch_total", "kept", "windows")
REQUIRED_CORPUS_META = (
    "run_utc",
    "input_sha256",
    "rows",
    "ok",
    "failed",
    "by_reason",
    "batch_count",
    "results",
)


class GateError(RuntimeError):
    pass


def _read_meta(path, required):
    meta_path = pathlib.Path(path)
    if not meta_path.exists():
        raise GateError(f"missing meta: {path}")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    missing = [key for key in required if key not in meta]
    if missing:
        raise GateError(f"{path}: missing required keys: {', '.join(missing)}")
    return meta


def check(xlsx, run_meta, corpus_meta, expected_batches=None):
    workbook = openpyxl.load_workbook(xlsx)
    ws = workbook.active
    headers = [cell.value for cell in ws[1]]
    validate_headers(headers)
    index = {name: position for position, name in enumerate(headers)}
    rows = [
        row
        for row in ws.iter_rows(min_row=2, values_only=True)
        if any(value not in (None, "") for value in row)
    ]
    if not rows:
        raise GateError("xlsx has zero usable rows")
    keys = []
    for row in rows:
        url = str(row[index["URL"]] or "").strip()
        if not url:
            raise GateError("empty URL in xlsx")
        published = str(row[index["Date"]] or "").strip()
        try:
            day = datetime.date.fromisoformat(published)
        except ValueError as error:
            raise GateError(f"invalid date in xlsx: {published}") from error
        if day.year != 2025:
            raise GateError(f"non-2025 date in xlsx: {published}")
        keys.append(normalize_url(url))
    if len(set(keys)) != len(keys):
        raise GateError("duplicate URLs in xlsx")

    corpus_dir = pathlib.Path(corpus_meta).parent
    for row in rows:
        number = row[index["No"]]
        status = str(row[index["Fulltext_Status"]] or "").strip()
        if status not in FULLTEXT_STATUSES or status == "pending":
            raise GateError(f"row {number} has invalid Fulltext_Status: {status or '<empty>'}")
        docx = str(row[index["Docx_File"]] or "").strip()
        if status == "ok":
            if not docx:
                raise GateError(f"row {number} is ok but has no Docx_File")
            if not (corpus_dir / docx).is_file():
                raise GateError(f"row {number} Docx_File is missing: {docx}")
        elif docx:
            raise GateError(f"row {number} is {status} but has Docx_File: {docx}")

    _read_meta(run_meta, REQUIRED_RUN_META)
    corpus = _read_meta(corpus_meta, REQUIRED_CORPUS_META)
    batch_count = int(corpus.get("batch_count", 0))
    if expected_batches is not None and batch_count != expected_batches:
        raise GateError(f"batch mismatch: expected {expected_batches}, corpus meta says {batch_count}")
    if int(corpus.get("rows", 0)) != len(rows):
        raise GateError(f"corpus rows {corpus.get('rows')} != xlsx rows {len(rows)}")
    if int(corpus.get("ok", 0)) + int(corpus.get("failed", 0)) != int(corpus.get("rows", 0)):
        raise GateError(
            f"corpus ok+failed {corpus.get('ok')}+{corpus.get('failed')} != rows {corpus.get('rows')}"
        )
    if len(corpus.get("results", [])) != len(rows):
        raise GateError(f"corpus results {len(corpus.get('results', []))} != xlsx rows {len(rows)}")
    xlsx_numbers = sorted(int(row[index["No"]]) for row in rows)
    result_numbers = []
    for result in corpus.get("results", []):
        try:
            result_numbers.append(int(result["No"]))
        except (KeyError, TypeError, ValueError) as error:
            raise GateError(f"invalid corpus result row: {result}") from error
        if result.get("status") == "ok":
            if not result.get("file"):
                raise GateError(f"row {result.get('No')} is ok but has no Docx_File")
        elif result.get("status") != "failed" or result.get("reason") not in FAILURE_REASONS:
            raise GateError(f"row {result.get('No')} has invalid status/reason: {result}")
    if sorted(result_numbers) != xlsx_numbers:
        raise GateError("corpus results do not cover the xlsx rows")
    results_by_number = {int(result["No"]): result for result in corpus.get("results", [])}
    for row in rows:
        number = int(row[index["No"]])
        result = results_by_number[number]
        status = str(row[index["Fulltext_Status"]] or "").strip()
        docx = str(row[index["Docx_File"]] or "").strip()
        result_ok = result.get("status") == "ok"
        if (status == "ok") != result_ok:
            raise GateError(
                f"row {number} status mismatch: xlsx {status} vs corpus {result.get('status')}"
            )
        if result_ok:
            if docx != (result.get("file") or ""):
                raise GateError(
                    f"row {number} Docx_File mismatch: "
                    f"xlsx {docx} vs corpus {result.get('file')}"
                )
        elif status != (result.get("reason") or ""):
            raise GateError(
                f"row {number} reason mismatch: xlsx {status} vs corpus {result.get('reason')}"
            )
    for result in corpus.get("results", []):
        if result.get("status") == "ok" and not (corpus_dir / result["file"]).is_file():
            raise GateError(f"row {result.get('No')} ok but file is missing: {result['file']}")
    expected_files = {
        str(result["file"]) for result in corpus.get("results", []) if result.get("status") == "ok"
    }
    actual_files = {path.name for path in corpus_dir.glob("*.docx")}
    if actual_files != expected_files:
        raise GateError(
            f"corpus docx mismatch: extra={sorted(actual_files - expected_files)} "
            f"missing={sorted(expected_files - actual_files)}"
        )
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate release inputs before publishing")
    parser.add_argument("--xlsx", default="output/articles-2025.xlsx")
    parser.add_argument("--run-meta", default="output/run-meta.json")
    parser.add_argument("--corpus-meta", default="corpus/corpus-meta.json")
    parser.add_argument("--expected-batches", type=int, default=None)
    args = parser.parse_args(argv)
    try:
        check(args.xlsx, args.run_meta, args.corpus_meta, args.expected_batches)
    except (GateError, ValueError) as error:
        print(f"release gate failed: {error}", file=sys.stderr)
        return 1
    print("release gate passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
