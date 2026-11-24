import hashlib
import json

import openpyxl
import pytest
from openpyxl import Workbook

from src import import_legacy, schema

OLD_HEADERS = [
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
    "translation_ok",
]


def write_legacy(path, count=180, headers=None):
    workbook = Workbook()
    ws = workbook.active
    ws.append(headers or OLD_HEADERS)
    for number in range(1, count + 1):
        signal = number % 2 == 0
        publisher = "Kementerian Agama Republik Indonesia" if number == 1 else "Kompas.com"
        title_original = (
            f"Microsoft Indonesia artikel {number}" if signal else f"Harga emas naik {number}"
        )
        title_id = f"Terjemahan {number}"
        snippet_original = (
            f"Azure dan Copilot&nbsp;nomor {number}" if signal else f"Pasar modal&nbsp;{number}"
        )
        ws.append(
            [
                number,
                publisher,
                title_id,
                "" if number == 3 else title_original,
                f"https://news.google.com/rss/articles/{number}",
                f"2025-{((number - 1) % 12) + 1:02d}-10",
                "investasi microsoft di Indonesia tahun 2025",
                "Microsoft elevAIte di Indonesia 2025" if number % 5 == 0 else None,
                snippet_original,
                snippet_original,
                "unknown" if number == 4 else ("en" if number % 3 == 0 else "id"),
                "True",
            ]
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)
    return path


def read_output(path):
    ws = openpyxl.load_workbook(path).active
    headers = [cell.value for cell in ws[1]]
    return headers, list(ws.iter_rows(min_row=2, values_only=True))


def test_import_maps_old_columns_and_keeps_all_rows(tmp_path):
    source = write_legacy(tmp_path / "articles-2025-4.xlsx")
    out = tmp_path / "output" / "articles-2025.xlsx"
    meta_path = tmp_path / "output" / "run-meta.json"

    import_legacy.import_file(str(source), str(out), str(meta_path))

    headers, rows = read_output(out)
    assert headers == schema.COLUMNS
    assert len(rows) == 180
    index = {name: position for position, name in enumerate(headers)}
    first = rows[0]
    assert first[index["Title"]] == "Harga emas naik 1"
    assert first[index["Snippet"]] == "Pasar modal 1"
    assert first[index["Source_Lang"]] == "id"
    assert first[index["Query_Group"]] == "legacy"
    assert first[index["Found_In_Groups"]] == "legacy"
    assert first[index["Publisher_Domain"]] in ("", None)
    assert first[index["Source_Type"]] == "government"
    assert first[index["Government_Body"]] == "Kemenag"
    assert first[index["Microsoft_Signal"]] == "no"
    assert first[index["Microsoft_Mention"]] == "unknown"
    assert first[index["Analysis_Ready"]] == "review"
    assert first[index["Fulltext_Status"]] == "pending"
    assert first[index["Docx_File"]] in ("", None)
    second = rows[1]
    assert second[index["Title"]] == "Microsoft Indonesia artikel 2"
    assert second[index["Snippet"]] == "Azure dan Copilot nomor 2"
    assert second[index["Also_Found_In"]] is None
    assert second[index["Microsoft_Signal"]] == "yes"
    assert second[index["Analysis_Ready"]] == "yes"
    assert rows[2][index["Title"]] == "Terjemahan 3"
    assert rows[3][index["Source_Lang"]] == "unknown"
    assert rows[4][index["Also_Found_In"]] == "Microsoft elevAIte di Indonesia 2025"


def test_import_writes_legacy_run_meta(tmp_path):
    source = write_legacy(tmp_path / "articles-2025-4.xlsx")
    out = tmp_path / "audio.xlsx"
    meta_path = tmp_path / "run-meta.json"

    import_legacy.import_file(str(source), str(out), str(meta_path))

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["schema_version"] == 3
    assert meta["mode"] == "legacy"
    assert meta["source_release"] == "articles-2025-4"
    assert meta["source_asset_url"] == import_legacy.SOURCE_ASSET_URL
    assert meta["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert meta["rows"] == 180
    assert meta["microsoft_signal_yes"] == 90
    assert meta["microsoft_signal_no"] == 90
    assert meta["gov_rows"] == 1
    assert meta["by_government_body"] == {"Kemenag": 1}
    assert meta["errors"] == []
    assert sum(meta["by_source_lang"].values()) == 180
    assert meta["by_source_lang"]["unknown"] == 1


def test_import_rejects_wrong_row_count(tmp_path):
    source = write_legacy(tmp_path / "short.xlsx", count=179)
    with pytest.raises(import_legacy.LegacyImportError, match="180"):
        import_legacy.import_file(
            str(source), str(tmp_path / "out.xlsx"), str(tmp_path / "meta.json")
        )


def test_import_rejects_missing_old_header(tmp_path):
    headers = [header for header in OLD_HEADERS if header != "Title_Original"]
    source = write_legacy(tmp_path / "bad.xlsx", headers=headers)
    with pytest.raises(import_legacy.LegacyImportError, match="Title_Original"):
        import_legacy.import_file(
            str(source), str(tmp_path / "out.xlsx"), str(tmp_path / "meta.json")
        )


def test_import_cli_defaults_and_exit_code(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    source = write_legacy(tmp_path / "output" / "legacy" / "articles-2025-4.xlsx")
    assert (
        import_legacy.main(
            [
                "--input",
                str(source),
                "--out",
                str(tmp_path / "output" / "articles-2025.xlsx"),
            ]
        )
        == 0
    )
    assert (tmp_path / "output" / "articles-2025.xlsx").exists()
    assert (tmp_path / "output" / "run-meta.json").exists()
