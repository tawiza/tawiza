"""Advanced document parser using Docling for PDF/DOCX/XLSX extraction.

Docling provides:
- OCR for scanned documents
- Table structure recognition
- Multi-format support (PDF, DOCX, XLSX, HTML, images)
- Structured output with metadata

This parser is optimized for French government documents (gouv.fr, INSEE, etc.).
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

# Optional imports with fallbacks
try:
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter

    DOCLING_AVAILABLE = True
except ImportError:
    DOCLING_AVAILABLE = False
    logger.warning("Docling not installed. PDF parsing will use fallback.")

try:
    import pdfplumber

    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


@dataclass
class ParsedTable:
    """Represents an extracted table from a document."""

    name: str
    data: list[list[str]]
    headers: list[str] = field(default_factory=list)
    page: int | None = None

    def to_dataframe(self) -> Any:
        """Convert to pandas DataFrame if available."""
        if not PANDAS_AVAILABLE:
            return self.data
        import pandas as pd

        if self.headers:
            return pd.DataFrame(self.data, columns=self.headers)
        return pd.DataFrame(self.data)


@dataclass
class ParsedDocument:
    """Result of document parsing with structured content."""

    text: str
    tables: list[ParsedTable] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    pages: int = 0
    source: str = ""
    format: str = ""
    language: str = "fra"

    def to_markdown(self) -> str:
        """Export document as markdown."""
        md_parts = [f"# {self.metadata.get('title', 'Document')}\n"]

        if self.metadata:
            md_parts.append("## Metadata\n")
            for key, value in self.metadata.items():
                if key != "title":
                    md_parts.append(f"- **{key}**: {value}\n")

        md_parts.append("\n## Content\n")
        md_parts.append(self.text)

        if self.tables:
            md_parts.append("\n## Tables\n")
            for i, table in enumerate(self.tables, 1):
                md_parts.append(f"\n### Table {i}: {table.name}\n")
                if table.headers:
                    md_parts.append("| " + " | ".join(table.headers) + " |\n")
                    md_parts.append("|" + "|".join(["---"] * len(table.headers)) + "|\n")
                for row in table.data[:10]:  # Limit to 10 rows for preview
                    md_parts.append("| " + " | ".join(str(c) for c in row) + " |\n")

        return "".join(md_parts)


class DoclingParser:
    """Advanced document parser with Docling + pdfplumber fallback.

    Optimized for French government documents:
    - INSEE statistics (PDF tables)
    - BODACC/BOAMP announcements (HTML/PDF)
    - Prefecture documents (scanned PDFs)
    - Regional economic reports
    """

    def __init__(
        self,
        lang: str = "fra",
        enable_ocr: bool = True,
        extract_tables: bool = True,
        timeout: float = 60.0,
    ):
        """Initialize parser with configuration.

        Args:
            lang: Document language (default: French)
            enable_ocr: Enable OCR for scanned documents
            extract_tables: Extract table structures
            timeout: Download timeout for URLs
        """
        self.lang = lang
        self.enable_ocr = enable_ocr
        self.extract_tables = extract_tables
        self.timeout = timeout
        self._converter: DocumentConverter | None = None

    @property
    def converter(self) -> DocumentConverter | None:
        """Lazy initialization of Docling converter."""
        if self._converter is None and DOCLING_AVAILABLE:
            try:
                pipeline_options = PdfPipelineOptions()
                pipeline_options.do_ocr = self.enable_ocr
                pipeline_options.do_table_structure = self.extract_tables
                self._converter = DocumentConverter(pipeline_options=pipeline_options)
            except Exception as e:
                logger.warning(f"Failed to initialize Docling: {e}")
        return self._converter

    async def parse(self, source: str | Path) -> ParsedDocument:
        """Parse a document from URL or file path.

        Args:
            source: URL or local file path

        Returns:
            ParsedDocument with extracted content
        """
        source_str = str(source)

        # Handle URLs
        if source_str.startswith(("http://", "https://")):
            return await self._parse_url(source_str)

        # Handle local files
        path = Path(source_str)
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {path}")

        return await self._parse_file(path)

    async def _parse_url(self, url: str) -> ParsedDocument:
        """Download and parse a document from URL."""
        logger.info(f"Downloading document: {url}")

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()

            # Determine format from content-type or URL
            content_type = response.headers.get("content-type", "")
            suffix = self._get_suffix(url, content_type)

            # Save to temp file and parse
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(response.content)
                temp_path = Path(f.name)

            try:
                result = await self._parse_file(temp_path)
                result.source = url
                return result
            finally:
                temp_path.unlink(missing_ok=True)

    def _get_suffix(self, url: str, content_type: str) -> str:
        """Determine file suffix from URL or content-type."""
        url_lower = url.lower()
        if url_lower.endswith(".pdf") or "pdf" in content_type:
            return ".pdf"
        elif url_lower.endswith(".docx") or "wordprocessing" in content_type:
            return ".docx"
        elif url_lower.endswith(".xlsx") or "spreadsheet" in content_type:
            return ".xlsx"
        elif url_lower.endswith(".html") or "html" in content_type:
            return ".html"
        return ".pdf"  # Default to PDF

    async def _parse_file(self, path: Path) -> ParsedDocument:
        """Parse a local file."""
        suffix = path.suffix.lower()
        logger.info(f"Parsing document: {path} (format: {suffix})")

        # Try Docling first for best results
        if DOCLING_AVAILABLE and self.converter:
            try:
                return self._parse_with_docling(path)
            except Exception as e:
                logger.warning(f"Docling parsing failed, trying fallback: {e}")

        # Fallback to pdfplumber for PDFs
        if suffix == ".pdf" and PDFPLUMBER_AVAILABLE:
            return self._parse_with_pdfplumber(path)

        # Last resort: basic text extraction
        return self._parse_basic(path)

    def _parse_with_docling(self, path: Path) -> ParsedDocument:
        """Parse using Docling (best quality)."""
        result = self.converter.convert(str(path))
        doc = result.document

        # Extract tables
        tables = []
        if self.extract_tables:
            for i, table in enumerate(getattr(doc, "tables", [])):
                try:
                    df = table.to_dataframe()
                    tables.append(
                        ParsedTable(
                            name=f"Table_{i + 1}",
                            data=df.values.tolist(),
                            headers=df.columns.tolist() if hasattr(df, "columns") else [],
                            page=getattr(table, "page", None),
                        )
                    )
                except Exception as e:
                    logger.debug(f"Failed to extract table {i}: {e}")

        return ParsedDocument(
            text=doc.export_to_markdown(),
            tables=tables,
            metadata=dict(getattr(doc, "metadata", {})),
            pages=getattr(doc, "num_pages", 0),
            source=str(path),
            format=path.suffix.lower().lstrip("."),
            language=self.lang,
        )

    def _parse_with_pdfplumber(self, path: Path) -> ParsedDocument:
        """Parse PDF using pdfplumber (fallback)."""
        text_parts = []
        tables = []

        with pdfplumber.open(path) as pdf:
            for i, page in enumerate(pdf.pages):
                # Extract text
                page_text = page.extract_text() or ""
                text_parts.append(f"## Page {i + 1}\n{page_text}")

                # Extract tables
                if self.extract_tables:
                    for j, table in enumerate(page.extract_tables()):
                        if table:
                            tables.append(
                                ParsedTable(
                                    name=f"Table_{i + 1}_{j + 1}",
                                    data=table[1:] if len(table) > 1 else [],
                                    headers=table[0] if table else [],
                                    page=i + 1,
                                )
                            )

            return ParsedDocument(
                text="\n\n".join(text_parts),
                tables=tables,
                metadata={"pages": len(pdf.pages)},
                pages=len(pdf.pages),
                source=str(path),
                format="pdf",
                language=self.lang,
            )

    def _parse_basic(self, path: Path) -> ParsedDocument:
        """Basic text extraction for unsupported formats."""
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            text = path.read_text(encoding="latin-1")

        return ParsedDocument(
            text=text,
            source=str(path),
            format=path.suffix.lower().lstrip("."),
            language=self.lang,
        )

    def parse_sync(self, source: str | Path) -> ParsedDocument:
        """Synchronous version of parse() for non-async contexts."""
        import asyncio

        return asyncio.get_event_loop().run_until_complete(self.parse(source))


# Convenience function for quick parsing
async def parse_document(
    source: str | Path,
    lang: str = "fra",
    extract_tables: bool = True,
) -> ParsedDocument:
    """Quick document parsing helper.

    Args:
        source: URL or file path
        lang: Document language
        extract_tables: Whether to extract tables

    Returns:
        ParsedDocument with content
    """
    parser = DoclingParser(lang=lang, extract_tables=extract_tables)
    return await parser.parse(source)
