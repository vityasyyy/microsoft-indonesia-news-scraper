"""Release gate: refuse to publish an empty, out-of-scope, or incomplete corpus."""
import argparse
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
        if row[index["URL"]]
    ]
    if not rows:
        raise GateError("xlsx has zero usable rows")
    for row in rows:
        published = row[index["Date"]]
        if str(published)[:4] != "2025":
            raise GateError(f"non-2025 date in xlsx: {published}")
    keys = [normalize_url(str(row[index["URL"]])) for row in rows]
    if len(set(keys)) != len(keys):
        raise GateError("duplicate URLs in xlsx")

    _read_meta(run_meta, REQUIRED_RUN_META)
    corpus = _read_meta(corpus_meta, REQUIRED_CORPUS_META)
    batch_count = int(corpus.get("batch_count", 0))
    if expected_batches is not None and batch_count != expected_batches:
        raise GateError(f"batch mismatch: expected {expected_batches}, corpus meta says {batch_count}")
    if int(corpus.get("rows", 0)) != len(rows):
        raise GateError(f"corpus rows {corpus.get('rows')} != xlsx rows {len(rows)}")
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
