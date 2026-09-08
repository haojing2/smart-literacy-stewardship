from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Protocol
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

PDF_MIME_TYPE = "application/pdf"
DOCX_MIME_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)
WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
WORD_PARAGRAPH = f"{{{WORD_NAMESPACE}}}p"
WORD_TEXT = f"{{{WORD_NAMESPACE}}}t"
WORD_TAB = f"{{{WORD_NAMESPACE}}}tab"
WORD_BREAKS = {f"{{{WORD_NAMESPACE}}}br", f"{{{WORD_NAMESPACE}}}cr"}


class DocumentParsingError(ValueError):
    pass


class NoExtractableTextError(DocumentParsingError):
    pass


class PdfMarkdownConverter(Protocol):
    """A replaceable PDF-to-Markdown engine (for example MinerU or Docling)."""

    def convert(self, pdf_path: Path) -> str: ...


class PyMuPDF4LLMConverter:
    """Default local converter; isolated so callers are not vendor-coupled."""

    def convert(self, pdf_path: Path) -> str:
        try:
            import pymupdf
            import pymupdf4llm
        except ImportError as exc:
            raise DocumentParsingError(
                "pymupdf4llm is required for PDF-to-Markdown conversion"
            ) from exc
        try:
            # Passing a filename lets pymupdf4llm open the document itself,
            # but it does not own a deterministic close point on Windows.
            # Owning the document here prevents the source PDF from remaining
            # locked after conversion.
            document = pymupdf.open(pdf_path)
            try:
                return pymupdf4llm.to_markdown(document)
            finally:
                document.close()
        except Exception as exc:
            raise DocumentParsingError(
                "Unable to convert the PDF to Markdown with pymupdf4llm"
            ) from exc


class DocumentParserService:
    """Extract complete plain text from supported documents without OCR or AI."""

    def __init__(self, markdown_converter: PdfMarkdownConverter | None = None) -> None:
        self._markdown_converter = markdown_converter or PyMuPDF4LLMConverter()

    def parse_pdf_to_markdown(self, *, project_id: int, pdf_path: Path) -> str:
        """Convert one local PDF and persist its Markdown in the project KB.

        This is deliberately separate from the existing plain-text ``parse``
        API, so an uploader or future job runner can opt into conversion
        without coupling itself to PyMuPDF4LLM.
        """
        if not pdf_path.is_file():
            raise DocumentParsingError("The source PDF file does not exist")
        if pdf_path.suffix.lower() != ".pdf":
            raise DocumentParsingError("Only PDF files can be converted to Markdown")

        markdown = self._markdown_converter.convert(pdf_path)
        if not isinstance(markdown, str) or not markdown.strip():
            raise DocumentParsingError("PDF conversion produced empty Markdown")

        from app.services.knowledge_base_path_service import KnowledgeBasePathService

        destination = KnowledgeBasePathService().parsed_markdown_file(
            project_id, pdf_path.name
        )
        try:
            destination.write_text(markdown, encoding="utf-8")
        except OSError as exc:
            raise DocumentParsingError("Unable to save parsed Markdown") from exc
        return markdown

    def parse(self, *, path: Path, mime_type: str) -> str:
        if not path.is_file():
            raise DocumentParsingError("The stored research file does not exist")
        if mime_type == PDF_MIME_TYPE:
            text = self._extract_pdf(path)
            empty_message = (
                "PDF contains no extractable text. It may be a scanned PDF; "
                "OCR is not supported in this version."
            )
        elif mime_type == DOCX_MIME_TYPE:
            text = self._extract_docx(path)
            empty_message = "DOCX contains no extractable text"
        else:
            raise DocumentParsingError("Only PDF and DOCX files can be parsed")

        cleaned_text = self.clean_text(text)
        if not cleaned_text or not any(char.isalnum() for char in cleaned_text):
            raise NoExtractableTextError(empty_message)
        return cleaned_text

    @staticmethod
    def clean_text(text: str) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        visible_characters: list[str] = []
        for character in text:
            if character in {"\n", "\t"}:
                visible_characters.append(character)
            elif unicodedata.category(character) not in {"Cc", "Cf"}:
                visible_characters.append(character)

        normalized = "".join(visible_characters)
        normalized = re.sub(r"[^\S\n]+", " ", normalized)
        normalized = "\n".join(line.strip() for line in normalized.split("\n"))
        normalized = re.sub(r"\n{3,}", "\n\n", normalized)
        return normalized.strip()

    @staticmethod
    def _extract_pdf(path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise DocumentParsingError(
                "PDF text extraction dependency is not installed"
            ) from exc
        try:
            reader = PdfReader(path)
            if reader.is_encrypted:
                try:
                    unlocked = reader.decrypt("")
                except Exception as exc:
                    raise DocumentParsingError(
                        "Encrypted PDF files are not supported"
                    ) from exc
                if unlocked == 0:
                    raise DocumentParsingError(
                        "Encrypted PDF files are not supported"
                    )
            return "\n\n".join((page.extract_text() or "") for page in reader.pages)
        except DocumentParsingError:
            raise
        except Exception as exc:
            raise DocumentParsingError("Unable to read the PDF document") from exc

    @staticmethod
    def _extract_docx(path: Path) -> str:
        try:
            with ZipFile(path) as document:
                xml_content = document.read("word/document.xml")
            root = ElementTree.fromstring(xml_content)
        except (BadZipFile, KeyError, ElementTree.ParseError, OSError) as exc:
            raise DocumentParsingError("Unable to read the DOCX document") from exc

        paragraphs: list[str] = []
        for paragraph in root.iter(WORD_PARAGRAPH):
            parts: list[str] = []
            for node in paragraph.iter():
                if node.tag == WORD_TEXT and node.text:
                    parts.append(node.text)
                elif node.tag == WORD_TAB:
                    parts.append("\t")
                elif node.tag in WORD_BREAKS:
                    parts.append("\n")
            paragraphs.append("".join(parts))
        return "\n".join(paragraphs)
