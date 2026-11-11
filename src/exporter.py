"""Schema v2 xlsx writer, run-meta writer, and corpus status updater."""
import json

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

from src.schema import COLUMNS, FULLTEXT_STATUSES, validate_headers

WIDTHS = {
    "No": 6,
    "Publisher": 18,
    "Publisher_Domain": 22,
    "Source_Type": 12,
    "Query_Group": 12,
    "Found_In_Groups": 20,
    "Title": 60,
    "Snippet": 60,
    "URL": 50,
    "Date": 12,
    "Keyword_Found": 34,
    "Also_Found_In": 30,
    "Source_Lang": 11,
    "Government_Body": 24,
    "Fulltext_Status": 15,
    "Docx_File": 42,
}
FORMULA_PREFIXES = ("=", "+", "-", "@")


def _set_cell(ws, row, column, value):
    cell = ws.cell(row=row, column=column)
    cell.value = value
    if isinstance(value, str) and value.startswith(FORMULA_PREFIXES):
        cell.data_type = "s"
    return cell


def _value(row, column):
    value = row.get(column, "")
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    if value is None:
        return ""
    return value


def export_xlsx(rows, path):
    workbook = Workbook()
    ws = workbook.active
    ws.title = "articles-2025"
    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(bold=True, color="FFFFFF")
    for column, name in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=column, value=name)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    for index, row in enumerate(rows, start=1):
        for column, name in enumerate(COLUMNS, start=1):
            _set_cell(ws, index + 1, column, index if name == "No" else _value(row, name))
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for column, name in enumerate(COLUMNS, start=1):
        ws.column_dimensions[ws.cell(row=1, column=column).column_letter].width = WIDTHS[name]
    workbook.save(path)
    return path


def write_meta(meta, path):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(meta, handle, ensure_ascii=False, indent=2)
    return path


def update_fulltext_status(xlsx, results):
    """Write Fulltext_Status/Docx_File from per-row corpus results."""
    workbook = load_workbook(xlsx)
    ws = workbook.active
    headers = [cell.value for cell in ws[1]]
    validate_headers(headers)
    index = {name: position for position, name in enumerate(headers)}
    by_number = {}
    for result in results:
        try:
            by_number[int(result["No"])] = result
        except (KeyError, TypeError, ValueError):
            continue
    for row_number in range(2, ws.max_row + 1):
        raw_number = ws.cell(row=row_number, column=index["No"] + 1).value
        if raw_number is None:
            continue
        try:
            number = int(raw_number)
        except (TypeError, ValueError):
            continue
        result = by_number.get(number)
        if result is None:
            continue
        ok = result.get("status") == "ok" and bool(result.get("file"))
        status = "ok" if ok else (result.get("reason") or "internal_error")
        if status not in FULLTEXT_STATUSES:
            status = "internal_error"
        _set_cell(ws, row_number, index["Fulltext_Status"] + 1, status)
        _set_cell(ws, row_number, index["Docx_File"] + 1, result.get("file", "") if ok else "")
    workbook.save(xlsx)
    return xlsx
