"""Assemble one docx: Heading-1 title, metadata, original full body."""
from docx import Document


def build(path, title, meta, body):
    text = (body or "").strip()
    if not text:
        raise ValueError("empty article body")
    doc = Document()
    doc.add_heading((title or "Tanpa judul").strip(), level=1)
    doc.add_paragraph(
        f"Publisher: {meta.get('Publisher', '')} | "
        f"Date: {meta.get('Date', '')} | "
        f"Keyword: {meta.get('Keyword_Found', '')} | "
        f"Accessed: {meta.get('Accessed', '')} | "
        f"Language: {meta.get('Language', 'unknown')}"
    )
    doc.add_paragraph(f"URL: {meta.get('URL', '')}")
    if meta.get("Resolved_URL"):
        doc.add_paragraph(f"Resolved URL: {meta['Resolved_URL']}")
    for paragraph in text.split("\n"):
        paragraph = paragraph.strip()
        if paragraph:
            doc.add_paragraph(paragraph)
    doc.save(path)
    return path
