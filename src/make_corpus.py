"""Wire xlsx rows -> pooled fetch/translate/build -> corpus/ + failed.csv + meta."""
import csv
import datetime
import json
import os
import pathlib
import re
from concurrent.futures import ThreadPoolExecutor

import openpyxl

from src import downloader, docx_builder, translator

XLSX_IN = "output/articles-2025.xlsx"
OUT_DIR = "corpus"
LIMIT = int(os.environ.get("LIMIT", "0") or 0)

def slugify(text, fallback):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:60].strip("-")
    return s or fallback

def read_rows(xlsx):
    wb = openpyxl.load_workbook(xlsx)
    ws = wb.active
    headers = [c.value for c in ws[1]]
    idx = {h: headers.index(h) for h in ("No", "Publisher", "Title_ID", "Title_Original", "URL", "Date", "Keyword_Found")}
    rows = []
    for r in list(ws.rows)[1:]:
        v = [c.value for c in r]
        rows.append({
            "No": v[idx["No"]],
            "Publisher": v[idx["Publisher"]] or "",
            "Title": (v[idx["Title_ID"]] or v[idx["Title_Original"]] or "").strip(),
            "URL": (v[idx["URL"]] or "").strip(),
            "Date": str(v[idx["Date"]] or ""),
            "Keyword_Found": v[idx["Keyword_Found"]] or "",
        })
    return [r for r in rows if r["URL"]]

def process_row(row, outdir):
    n = int(row["No"])
    pub = slugify(row["Publisher"], "unknown")
    got = downloader.fetch(row["URL"])
    if not got["ok"]:
        return {"status": "failed", "No": n, "URL": row["URL"], "Publisher": row["Publisher"], "Keyword_Found": row["Keyword_Found"], "reason": got["reason"], "stage": got["stage"]}
    lang = translator.detect_lang((row["Title"] or "") + " " + (got["text"] or ""))
    if lang == "en":
        body, ok = translator.translate_en_to_id(got["text"])
        if not ok:
            return {"status": "failed", "No": n, "URL": row["URL"], "Publisher": row["Publisher"], "Keyword_Found": row["Keyword_Found"], "reason": "translate_failed", "stage": "translate"}
    else:
        body = got["text"]
    title = row["Title"] or "Tanpa judul"
    fname = f"{n:03d}_{pub}_{slugify(title, 'article')}.docx"
    meta = {"Publisher": row["Publisher"], "Date": row["Date"], "URL": row["URL"], "Keyword_Found": row["Keyword_Found"], "Accessed": datetime.date.today().isoformat()}
    docx_builder.build(str(pathlib.Path(outdir) / fname), title, meta, body)
    return {"status": "ok", "No": n, "file": fname}

def main():
    if not pathlib.Path(XLSX_IN).exists():
        print(f"missing {XLSX_IN}: run `make` scrape first (`uv run python -m src.scrape`)")
        return 1
    outdir = pathlib.Path(OUT_DIR)
    outdir.mkdir(parents=True, exist_ok=True)
    rows = read_rows(XLSX_IN)
    if LIMIT > 0:
        rows = rows[:LIMIT]
    results = []
    with ThreadPoolExecutor(max_workers=downloader.MAX_WORKERS) as pool:
        for res in pool.map(lambda r: process_row(r, str(outdir)), rows):
            results.append(res)
    ok = [r for r in results if r["status"] == "ok"]
    failed = [r for r in results if r["status"] != "ok"]
    with open(outdir / "failed.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["No", "URL", "Publisher", "Keyword_Found", "reason", "stage"])
        w.writeheader()
        w.writerows([{"No": r["No"], "URL": r["URL"], "Publisher": r["Publisher"], "Keyword_Found": r["Keyword_Found"], "reason": r["reason"], "stage": r["stage"]} for r in failed])
    by_reason = {}
    for r in failed:
        by_reason[r["reason"]] = by_reason.get(r["reason"], 0) + 1
    with open(outdir / "corpus-meta.json", "w", encoding="utf-8") as f:
        json.dump({"run_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "xlsx": XLSX_IN, "rows": len(rows), "ok": len(ok), "failed": len(failed), "by_reason": by_reason}, f, ensure_ascii=False, indent=2)
    print(f"rows={len(rows)} ok={len(ok)} failed={len(failed)} dir={OUT_DIR}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
