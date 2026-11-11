"""Wire xlsx rows -> pooled fetch/extract/build -> corpus output + meta."""
import csv
import datetime
import hashlib
import json
import os
import pathlib
import re
from concurrent.futures import ThreadPoolExecutor

import openpyxl

from src import downloader, docx_builder, exporter, language
from src.schema import FAILED_COLUMNS, SchemaError, validate_headers

XLSX_IN = "output/articles-2025.xlsx"
FULL_DIR = "corpus"
PREVIEW_DIR = "corpus-preview"
DEFAULT_WORKERS = downloader.MAX_WORKERS


def slugify(text, fallback):
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:60].strip("-")
    return slug or fallback


def utc_today():
    return datetime.datetime.now(datetime.timezone.utc).date().isoformat()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_rows(xlsx):
    workbook = openpyxl.load_workbook(xlsx)
    ws = workbook.active
    headers = [cell.value for cell in ws[1]]
    validate_headers(headers)
    index = {name: position for position, name in enumerate(headers)}
    rows = []
    for values in list(ws.rows)[1:]:
        cells = [cell.value for cell in values]
        rows.append(
            {
                "No": cells[index["No"]],
                "Publisher": cells[index["Publisher"]] or "",
                "Title": (cells[index["Title"]] or "").strip(),
                "URL": (cells[index["URL"]] or "").strip(),
                "Date": str(cells[index["Date"]] or ""),
                "Keyword_Found": cells[index["Keyword_Found"]] or "",
            }
        )
    return [row for row in rows if row["URL"]]


def batch_rows(rows, index, count):
    if count < 1:
        raise ValueError("BATCH_COUNT must be >= 1")
    if not 0 <= index < count:
        raise ValueError("BATCH_INDEX must be within 0..BATCH_COUNT-1")
    return rows[index::count]


def resolve_outdir(limit, batch_count, batch_index, preview=False):
    if batch_count > 1:
        return f"corpus-batch-{batch_index}"
    if preview or limit > 0:
        return PREVIEW_DIR
    return FULL_DIR


def config_from_env(env=None):
    env = os.environ if env is None else env
    limit = int(env.get("LIMIT", "0") or 0)
    batch_count = int(env.get("BATCH_COUNT", "1") or 1)
    batch_index = int(env.get("BATCH_INDEX", "0") or 0)
    workers = int(env.get("CORPUS_WORKERS", str(DEFAULT_WORKERS)) or DEFAULT_WORKERS)
    preview_flag = (env.get("PREVIEW", "") or "").strip().lower() in ("1", "true", "yes")
    if limit < 0:
        raise ValueError("LIMIT must be >= 0")
    if workers < 1:
        raise ValueError("CORPUS_WORKERS must be >= 1")
    if batch_count < 1:
        raise ValueError("BATCH_COUNT must be >= 1")
    if not 0 <= batch_index < batch_count:
        raise ValueError("BATCH_INDEX must be within 0..BATCH_COUNT-1")
    out_dir = env.get("CORPUS_OUT") or resolve_outdir(limit, batch_count, batch_index, preview_flag)
    full = out_dir == FULL_DIR and batch_count == 1 and limit == 0
    return {
        "xlsx": env.get("CORPUS_XLSX", XLSX_IN),
        "limit": limit,
        "batch_count": batch_count,
        "batch_index": batch_index,
        "workers": workers,
        "out_dir": out_dir,
        "preview": out_dir == PREVIEW_DIR,
        "clear_docx": full,
        "update_xlsx": full,
    }


def clear_stale_docx(outdir):
    for path in pathlib.Path(outdir).glob("*.docx"):
        path.unlink()


def process_row(row, outdir, accessed=None):
    number = int(row["No"])
    publisher_slug = slugify(row["Publisher"], "unknown")
    fetched = downloader.fetch(row["URL"])
    base = {
        "No": number,
        "URL": row["URL"],
        "Resolved_URL": fetched.get("resolved_url") or "",
        "Publisher": row.get("Publisher", ""),
        "Keyword_Found": row.get("Keyword_Found", ""),
    }
    if not fetched.get("ok"):
        return {
            "status": "failed",
            **base,
            "reason": fetched.get("reason") or "fetch_error",
            "stage": fetched.get("stage") or "fetch",
        }
    title = row["Title"] or "Tanpa judul"
    body = fetched.get("text") or ""
    lang = language.detect_lang(f"{title} {body[:2000]}")
    filename = f"{number:03d}_{publisher_slug}_{slugify(title, 'article')}.docx"
    meta = {
        "Publisher": row.get("Publisher", ""),
        "Date": row.get("Date", ""),
        "URL": row["URL"],
        "Resolved_URL": fetched.get("resolved_url") or "",
        "Keyword_Found": row.get("Keyword_Found", ""),
        "Accessed": accessed or utc_today(),
        "Language": lang,
    }
    try:
        docx_builder.build(str(pathlib.Path(outdir) / filename), title, meta, body)
    except Exception:
        return {"status": "failed", **base, "reason": "internal_error", "stage": "docx"}
    return {"status": "ok", **base, "file": filename, "language": lang}


def safe_process(row, outdir, accessed=None):
    """Any unexpected per-row error becomes an internal_error row."""
    try:
        return process_row(row, outdir, accessed)
    except Exception:
        return {
            "status": "failed",
            "No": row.get("No"),
            "URL": row.get("URL", ""),
            "Resolved_URL": "",
            "Publisher": row.get("Publisher", ""),
            "Keyword_Found": row.get("Keyword_Found", ""),
            "reason": "internal_error",
            "stage": "row",
        }


def write_failed(path, results):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FAILED_COLUMNS)
        writer.writeheader()
        for result in results:
            if result["status"] == "ok":
                continue
            writer.writerow({column: result.get(column, "") for column in FAILED_COLUMNS})
    return path


def build_meta(config, rows, results):
    by_reason = {}
    for result in results:
        if result["status"] != "ok":
            reason = result.get("reason") or "internal_error"
            by_reason[reason] = by_reason.get(reason, 0) + 1
    return {
        "run_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "xlsx": config["xlsx"],
        "input_sha256": sha256_file(config["xlsx"]),
        "rows": len(results),
        "ok": sum(1 for result in results if result["status"] == "ok"),
        "failed": sum(1 for result in results if result["status"] != "ok"),
        "by_reason": by_reason,
        "batch_index": config["batch_index"],
        "batch_count": config["batch_count"],
        "workers": config["workers"],
        "preview": config["out_dir"] == PREVIEW_DIR,
        "results": [
            {
                key: result.get(key)
                for key in (
                    "No",
                    "URL",
                    "Resolved_URL",
                    "Publisher",
                    "Keyword_Found",
                    "status",
                    "file",
                    "reason",
                    "stage",
                    "language",
                )
            }
            for result in results
        ],
    }


def main():
    try:
        config = config_from_env()
    except ValueError as error:
        print(error)
        return 1
    if not pathlib.Path(config["xlsx"]).exists():
        print(f"missing {config['xlsx']}: run `uv run python -m src.scrape` first")
        return 1
    try:
        rows = read_rows(config["xlsx"])
        rows = batch_rows(rows, config["batch_index"], config["batch_count"])
    except (SchemaError, ValueError) as error:
        print(error)
        return 1
    if config["limit"] > 0:
        rows = rows[: config["limit"]]
    outdir = pathlib.Path(config["out_dir"])
    outdir.mkdir(parents=True, exist_ok=True)
    if config["clear_docx"]:
        clear_stale_docx(outdir)
    results = []
    total = len(rows)
    with ThreadPoolExecutor(max_workers=config["workers"]) as pool:
        for result in pool.map(lambda row: safe_process(row, str(outdir)), rows):
            results.append(result)
            done = len(results)
            if done % 10 == 0 or done == total:
                ok = sum(1 for item in results if item["status"] == "ok")
                print(f"[{done}/{total}] ok={ok} failed={done - ok}", flush=True)
    write_failed(outdir / "failed.csv", results)
    if config["update_xlsx"]:
        exporter.update_fulltext_status(config["xlsx"], results)
    meta = build_meta(config, rows, results)
    exporter.write_meta(meta, outdir / "corpus-meta.json")
    print(f"rows={len(rows)} ok={meta['ok']} failed={meta['failed']} dir={outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
