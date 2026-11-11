import pytest

from src import schema


def test_schema_v2_columns_exact_order():
    assert schema.COLUMNS == [
        "No",
        "Publisher",
        "Publisher_Domain",
        "Source_Type",
        "Query_Group",
        "Found_In_Groups",
        "Title",
        "Snippet",
        "URL",
        "Date",
        "Keyword_Found",
        "Also_Found_In",
        "Source_Lang",
        "Government_Body",
        "Fulltext_Status",
        "Docx_File",
    ]


def test_validate_headers_accepts_schema_columns():
    schema.validate_headers(list(schema.COLUMNS))


def test_validate_headers_reports_missing_columns():
    with pytest.raises(schema.SchemaError) as exc:
        schema.validate_headers(["No", "Publisher", "Legacy_Column"])
    message = str(exc.value)
    assert "Publisher_Domain" in message
    assert "Title" in message
    assert "rebuild" in message
