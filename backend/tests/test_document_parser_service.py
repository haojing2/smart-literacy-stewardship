from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.services.document_parser_service import (
    DOCX_MIME_TYPE,
    PDF_MIME_TYPE,
    DocumentParserService,
    NoExtractableTextError,
)
from app.core.config import settings


class StubMarkdownConverter:
    def __init__(self, result: str = "# Parsed paper\n\nResearch body") -> None:
        self.result = result
        self.paths: list[Path] = []

    def convert(self, pdf_path: Path) -> str:
        self.paths.append(pdf_path)
        return self.result


def write_docx(path: Path, document_xml: str) -> None:
    with ZipFile(path, "w") as document:
        document.writestr("[Content_Types].xml", "<Types />")
        document.writestr("word/document.xml", document_xml)


def write_text_pdf(path: Path) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_reference = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): font_reference}
            )
        }
    )
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 72 720 Td (Complete research body text) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    with path.open("wb") as output:
        writer.write(output)


def test_clean_text_removes_controls_and_duplicate_whitespace() -> None:
    cleaned = DocumentParserService.clean_text(
        "  标题\x00\t   内容  \r\n\r\n\r\n 第二段\u200b  "
    )
    assert cleaned == "标题 内容\n\n第二段"


def test_extracts_complete_docx_body_in_document_order(tmp_path: Path) -> None:
    path = tmp_path / "study.docx"
    write_docx(
        path,
        """<?xml version="1.0" encoding="UTF-8"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
          <w:body>
            <w:p><w:r><w:t>研究对象</w:t></w:r><w:tab/><w:r><w:t>五年级学生</w:t></w:r></w:p>
            <w:p><w:r><w:t>完整正文第二段</w:t><w:br/><w:t>换行内容</w:t></w:r></w:p>
          </w:body>
        </w:document>""",
    )
    text = DocumentParserService().parse(path=path, mime_type=DOCX_MIME_TYPE)
    assert text == "研究对象 五年级学生\n完整正文第二段\n换行内容"


def test_extracts_text_layer_from_pdf(tmp_path: Path) -> None:
    path = tmp_path / "study.pdf"
    write_text_pdf(path)
    text = DocumentParserService().parse(path=path, mime_type=PDF_MIME_TYPE)
    assert "Complete research body text" in text


def test_scanned_or_blank_pdf_returns_explicit_no_ocr_error(tmp_path: Path) -> None:
    path = tmp_path / "scanned.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    with path.open("wb") as output:
        writer.write(output)

    with pytest.raises(NoExtractableTextError, match="scanned PDF.*OCR is not supported"):
        DocumentParserService().parse(path=path, mime_type=PDF_MIME_TYPE)


def test_pdf_markdown_is_saved_to_the_project_parsed_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    knowledge_base_root = tmp_path / "knowledge_bases"
    monkeypatch.setattr(settings, "knowledge_base_root", knowledge_base_root)
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    converter = StubMarkdownConverter()

    markdown = DocumentParserService(converter).parse_pdf_to_markdown(
        project_id=17,
        pdf_path=pdf_path,
    )

    destination = knowledge_base_root / "project_17" / "parsed" / "paper.md"
    assert markdown == "# Parsed paper\n\nResearch body"
    assert converter.paths == [pdf_path]
    assert destination.read_text(encoding="utf-8") == markdown


def test_pdf_markdown_conversion_has_clear_errors(tmp_path: Path) -> None:
    non_pdf = tmp_path / "notes.docx"
    non_pdf.write_bytes(b"content")

    with pytest.raises(DocumentParsingError, match="Only PDF"):
        DocumentParserService(StubMarkdownConverter()).parse_pdf_to_markdown(
            project_id=1,
            pdf_path=non_pdf,
        )

    with pytest.raises(DocumentParsingError, match="empty Markdown"):
        pdf_path = tmp_path / "paper.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n")
        DocumentParserService(StubMarkdownConverter("   ")).parse_pdf_to_markdown(
            project_id=1,
            pdf_path=pdf_path,
        )
