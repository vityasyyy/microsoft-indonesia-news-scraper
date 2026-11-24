"""Import the frozen 180-row articles-2025-4 asset into schema v3, no translation."""
import argparse
import datetime
import hashlib
import pathlib

import openpyxl

from src import exporter, filters
from src.language import clean_html
from src.schema import SCHEMA_VERSION

EXPECTED_ROWS = 180
SOURCE_RELEASE = "articles-2025-4"
SOURCE_ASSET_URL = (
    "https://github.com/vityasyyy/microsoft-indonesia-news-scraper/releases/download/"
    "articles-2025-4/articles-2025.xlsx"
)
REQUIRED_OLD_HEADERS = (
    "No",
    "Publisher",
    "Title_ID",
    "Title_Original",
    "URL",
    "Date",
    "Keyword_Found",
    "Also_Found_In",
    "Snippet_ID",
    "Snippet_Original",
    "Source_Lang",
)
SOURCE_LANGS = ("id", "en", "other", "unknown")
INPUT_DEFAULT = "output/legacy/articles-2025-4.xlsx"
OUT_DEFAULT = "output/articles-2025.xlsx"
META_DEFAULT = "output/run-meta.json"


class LegacyImportError(ValueError):
    """Raised when the legacy asset is missing columns or rows."""


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text(value):
    return "" if value is None else str(value).strip()


def _date(value):
    if value is None:
        return ""
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    return str(value).strip()


def read_old_rows(path, expected_rows=EXPECTED_ROWS):
    workbook = openpyxl.load_workbook(path, read_only=True)
    ws = workbook.active
    rows = ws.iter_rows(values_only=True)
    headers = [_text(value) for value in next(rows, ())]
    missing = [header for header in REQUIRED_OLD_HEADERS if header not in headers]
    if missing:
        raise LegacyImportError(
            "legacy xlsx is missing required columns: "
            + ", ".join(missing)
            + "; download the articles-2025-4 release asset"
        )
    records = [row for row in rows if any(value not in (None, "") for value in row)]
    if len(records) != expected_rows:
        raise LegacyImportError(
            f"expected exactly {expected_rows} data rows, found {len(records)}; "
            "the legacy release asset changed"
        )
    return headers, records


def convert_rows(headers, records):
    index = {name: position for position, name in enumerate(headers)}
    rows = []
    for record in records:
        publisher = _text(record[index["Publisher"]])
        title = _text(record[index["Title_Original"]]) or _text(record[index["Title_ID"]])
        snippet = clean_html(
            _text(record[index["Snippet_Original"]]) or _text(record[index["Snippet_ID"]])
        )
        source_lang = _text(record[index["Source_Lang"]]).lower()
        if source_lang not in SOURCE_LANGS:
            source_lang = "unknown"
        signal = "yes" if filters.has_microsoft_signal(f"{title} {snippet}") else "no"
        rows.append(
            {
                "No": record[index["No"]],
                "Publisher": publisher,
                "Publisher_Domain": "",
                "Source_Type": "government" if filters.government_body(publisher) else "other",
                "Query_Group": "legacy",
                "Found_In_Groups": "legacy",
                "Title": title,
                "Snippet": snippet,
                "URL": _text(record[index["URL"]]),
                "Date": _date(record[index["Date"]]),
                "Keyword_Found": _text(record[index["Keyword_Found"]]),
                "Also_Found_In": _text(record[index["Also_Found_In"]]),
                "Source_Lang": source_lang,
                "Microsoft_Signal": signal,
                "Microsoft_Mention": "unknown",
                "Analysis_Ready": "yes" if signal == "yes" else "review",
                "Government_Body": filters.government_body(publisher, title, snippet),
                "Fulltext_Status": "pending",
                "Docx_File": "",
            }
        )
    return rows


def _counts(rows, key):
    counts = {}
    for row in rows:
        value = row.get(key)
        if value:
            counts[value] = counts.get(value, 0) + 1
    return counts


def build_meta(rows, source_path):
    signal = _counts(rows, "Microsoft_Signal")
    return {
        "run_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "schema_version": SCHEMA_VERSION,
        "mode": "legacy",
        "source_release": SOURCE_RELEASE,
        "source_asset_url": SOURCE_ASSET_URL,
        "source_sha256": sha256_file(source_path),
        "rows": len(rows),
        "microsoft_signal_yes": signal.get("yes", 0),
        "microsoft_signal_no": signal.get("no", 0),
        "by_source_lang": _counts(rows, "Source_Lang"),
        "gov_rows": sum(1 for row in rows if row["Source_Type"] == "government"),
        "by_government_body": _counts(rows, "Government_Body"),
        "errors": [],
    }


def import_file(input_path, out_path, meta_path, expected_rows=EXPECTED_ROWS):
    source = pathlib.Path(input_path)
    if not source.is_file():
        raise LegacyImportError(
            f"missing legacy asset {source}: run ./scripts/fetch_legacy.sh first"
        )
    headers, records = read_old_rows(str(source), expected_rows)
    rows = convert_rows(headers, records)
    pathlib.Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(meta_path).parent.mkdir(parents=True, exist_ok=True)
    exporter.export_xlsx(rows, out_path)
    meta = build_meta(rows, str(source))
    exporter.write_meta(meta, meta_path)
    return meta


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Import the frozen articles-2025-4 180-row list into schema v3"
    )
    parser.add_argument("--input", default=INPUT_DEFAULT)
    parser.add_argument("--out", default=OUT_DEFAULT)
    args = parser.parse_args(argv)
    try:
        meta = import_file(args.input, args.out, META_DEFAULT)
    except (LegacyImportError, OSError, openpyxl.utils.exceptions.InvalidFileException) as error:
        print(error)
        return 1
    print(
        f"rows={meta['rows']} signal_yes={meta['microsoft_signal_yes']} "
        f"signal_no={meta['microsoft_signal_no']} out={args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
