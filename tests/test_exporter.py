import pytest
from openpyxl import Workbook, load_workbook

from src import exporter, schema


def row(**over):
    base = {
        "No": 1,
        "Publisher": "Kompas",
        "Publisher_Domain": "kompas.com",
        "Source_Type": "other",
        "Query_Group": "baseline",
        "Found_In_Groups": ["baseline"],
        "Title": "Judul asli",
        "Snippet": "Ringkasan asli",
        "URL": "https://x.com/1",
        "Date": "2025-03-10",
        "Keyword_Found": "k1",
        "Also_Found_In": [],
        "Source_Lang": "id",
        "Government_Body": "",
        "Fulltext_Status": "pending",
        "Docx_File": "",
    }
    base.update(over)
    return base


def test_export_creates_xlsx_with_schema_v2_headers(tmp_path):
    p = str(tmp_path / "out.xlsx")
    exporter.export_xlsx([row()], p)
    ws = load_workbook(p).active
    assert [c.value for c in ws[1]] == list(schema.COLUMNS)
    assert ws.max_row == 2


def test_export_joins_found_in_lists(tmp_path):
    p = str(tmp_path / "out.xlsx")
    exporter.export_xlsx([row(Also_Found_In=["k2", "k3"], Found_In_Groups=["baseline", "government"])], p)
    ws = load_workbook(p).active
    idx = {h: i for i, h in enumerate(schema.COLUMNS)}
    values = [c.value for c in ws[2]]
    assert values[idx["Also_Found_In"]] == "k2, k3"
    assert values[idx["Found_In_Groups"]] == "baseline, government"


@pytest.mark.parametrize("value", ["=1+1", "+1+1", "-1+1", "@SUM(A1)"])
def test_formula_like_strings_are_written_as_literal_text(tmp_path, value):
    p = str(tmp_path / "out.xlsx")
    exporter.export_xlsx([row(Title=value)], p)
    ws = load_workbook(p).active
    cell = ws.cell(row=2, column=schema.COLUMNS.index("Title") + 1)
    assert cell.data_type == "s"
    assert cell.value == value


def test_update_fulltext_status_writes_ok_file_and_failure_reason(tmp_path):
    p = str(tmp_path / "out.xlsx")
    exporter.export_xlsx([row(No=1), row(No=2, URL="https://x.com/2")], p)
    exporter.update_fulltext_status(
        p,
        [
            {"No": 1, "status": "ok", "file": "001_kompas_judul.docx"},
            {"No": 2, "status": "failed", "reason": "paywall"},
        ],
    )
    ws = load_workbook(p).active
    idx = {h: i for i, h in enumerate(schema.COLUMNS)}
    first = [c.value for c in ws[2]]
    second = [c.value for c in ws[3]]
    assert first[idx["Fulltext_Status"]] == "ok"
    assert first[idx["Docx_File"]] == "001_kompas_judul.docx"
    assert second[idx["Fulltext_Status"]] == "paywall"
    assert second[idx["Docx_File"]] in ("", None)


def test_update_fulltext_status_rejects_missing_headers(tmp_path):
    p = str(tmp_path / "old.xlsx")
    wb = Workbook()
    ws = wb.active
    ws.append(["No", "Legacy_Column", "Old_Title"])
    wb.save(p)
    with pytest.raises(schema.SchemaError):
        exporter.update_fulltext_status(p, [{"No": 1, "status": "ok", "file": "x.docx"}])


def test_unknown_reason_becomes_internal_error(tmp_path):
    p = str(tmp_path / "out.xlsx")
    exporter.export_xlsx([row(No=1)], p)
    exporter.update_fulltext_status(p, [{"No": 1, "status": "failed", "reason": "weird"}])
    ws = load_workbook(p).active
    idx = {h: i for i, h in enumerate(schema.COLUMNS)}
    assert ws.cell(row=2, column=idx["Fulltext_Status"] + 1).value == "internal_error"
