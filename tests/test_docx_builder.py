import pytest
from docx import Document

from src import docx_builder


def test_build_heading_meta_paragraphs_and_language(tmp_path):
    path = str(tmp_path / "001_test.docx")
    meta = {
        "Publisher": "Kompas.com",
        "Date": "2025-03-10",
        "URL": "https://news.google.com/rss/articles/abc",
        "Resolved_URL": "https://kompas.com/article",
        "Keyword_Found": "k1",
        "Accessed": "2026-11-11",
        "Language": "id",
    }
    body = "Paragraf satu tentang Microsoft.\n\nParagraf dua tentang Indonesia."
    docx_builder.build(path, "Judul Artikel", meta, body)
    doc = Document(path)
    assert doc.paragraphs[0].style.name.startswith("Heading 1")
    assert "Judul Artikel" in doc.paragraphs[0].text
    texts = [paragraph.text for paragraph in doc.paragraphs]
    assert any("Kompas.com" in text and "2025-03-10" in text for text in texts)
    assert any("Language: id" in text for text in texts)
    assert any("Resolved URL: https://kompas.com/article" in text for text in texts)
    assert any("Paragraf satu" in text for text in texts)
    assert any("Paragraf dua" in text for text in texts)


def test_build_omits_resolved_url_when_missing(tmp_path):
    path = str(tmp_path / "002_test.docx")
    docx_builder.build(path, "Judul", {"Language": "en"}, "Body")
    texts = [paragraph.text for paragraph in Document(path).paragraphs]
    assert not any(text.startswith("Resolved URL:") for text in texts)
    assert any("Language: en" in text for text in texts)


def test_build_rejects_empty_body(tmp_path):
    with pytest.raises(ValueError):
        docx_builder.build(str(tmp_path / "x.docx"), "T", {}, "   ")
