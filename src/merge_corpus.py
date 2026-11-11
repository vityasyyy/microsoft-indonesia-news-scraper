"""Merge corpus batch directories into one corpus/ and refresh xlsx statuses."""
import argparse
import csv
import datetime
import json
import pathlib
import shutil
import sys

from src import exporter
from src.make_corpus import sha256_file
from src.schema import FAILED_COLUMNS

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


class MergeError(RuntimeError):
    pass


def _read_meta(path, required):
    if not path.exists():
        raise MergeError(f"missing batch meta: {path}")
    meta = json.loads(path.read_text(encoding="utf-8"))
    missing = [key for key in required if key not in meta]
    if missing:
        raise MergeError(f"{path}: missing keys: {', '.join(missing)}")
    return meta


def merge(batch_dirs, outdir, xlsx, expected_batches=None):
    loaded = []
    for directory in batch_dirs:
        batch_dir = pathlib.Path(directory)
        meta = _read_meta(batch_dir / "corpus-meta.json", REQUIRED_CORPUS_META)
        loaded.append((batch_dir, meta))
    if not loaded:
        raise MergeError("no batch directories given")
    count = expected_batches or loaded[0][1].get("batch_count") or len(loaded)
    indexes = sorted(int(meta.get("batch_index", position)) for position, (_, meta) in enumerate(loaded))
    if len(loaded) != count or indexes != list(range(count)):
        raise MergeError(f"expected batches 0..{count - 1}, got indexes {indexes}")

    out = pathlib.Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    for stale in out.glob("*.docx"):
        stale.unlink()

    results = []
    failed_rows = []
    by_reason = {}
    for batch_dir, meta in loaded:
        for docx in batch_dir.glob("*.docx"):
            shutil.copy2(docx, out / docx.name)
        for result in meta.get("results", []):
            results.append(result)
            if result.get("status") != "ok":
                reason = result.get("reason") or "internal_error"
                by_reason[reason] = by_reason.get(reason, 0) + 1
        failed_csv = batch_dir / "failed.csv"
        if failed_csv.exists():
            with open(failed_csv, newline="", encoding="utf-8") as handle:
                failed_rows.extend(list(csv.DictReader(handle)))

    with open(out / "failed.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FAILED_COLUMNS)
        writer.writeheader()
        for row in failed_rows:
            writer.writerow({column: row.get(column, "") for column in FAILED_COLUMNS})

    meta = {
        "run_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "xlsx": xlsx,
        "input_sha256": "",
        "rows": len(results),
        "ok": sum(1 for result in results if result.get("status") == "ok"),
        "failed": sum(1 for result in results if result.get("status") != "ok"),
        "by_reason": by_reason,
        "batch_count": count,
        "batches": [
            {
                "batch_index": batch_meta.get("batch_index"),
                "rows": batch_meta.get("rows"),
                "ok": batch_meta.get("ok"),
                "failed": batch_meta.get("failed"),
                "run_utc": batch_meta.get("run_utc"),
            }
            for _, batch_meta in loaded
        ],
        "results": results,
    }
    exporter.update_fulltext_status(xlsx, results)
    meta["input_sha256"] = sha256_file(xlsx)
    (out / "corpus-meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return meta


def main(argv=None):
    parser = argparse.ArgumentParser(description="Merge corpus batch directories into one corpus/")
    parser.add_argument("--batches", nargs="+", required=True)
    parser.add_argument("--out", default="corpus")
    parser.add_argument("--xlsx", default="output/articles-2025.xlsx")
    parser.add_argument("--expected-batches", type=int, default=None)
    args = parser.parse_args(argv)
    try:
        meta = merge(args.batches, args.out, args.xlsx, args.expected_batches)
    except MergeError as error:
        print(error, file=sys.stderr)
        return 1
    print(f"rows={meta['rows']} ok={meta['ok']} failed={meta['failed']} dir={args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
