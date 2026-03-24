"""PDF Export API routes for professional report generation."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/export", tags=["Export"])

# Template directory
TEMPLATES_DIR = (
    Path(__file__).parent.parent.parent.parent.parent / "infrastructure" / "export" / "templates"
)


class ExportRequest(BaseModel):
    """Request model for PDF export."""

    conversation_id: str = Field(..., description="Conversation ID to export")
    content: str = Field(..., description="Markdown content to export")
    title: str = Field(default="Rapport TAJINE", description="Report title")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Extra metadata")
    format: str = Field(default="report", description="Template format: report or summary")


class ExportResponse(BaseModel):
    """Response model for export operations."""

    success: bool
    filename: str
    message: str


def _render_markdown_to_html(content: str) -> str:
    """
    Convert Markdown content to HTML.

    Uses markdown library with extensions for:
    - Tables (GFM style)
    - Fenced code blocks
    - Math formulas (via extension)
    """
    import markdown
    from markdown.extensions.codehilite import CodeHiliteExtension
    from markdown.extensions.fenced_code import FencedCodeExtension
    from markdown.extensions.tables import TableExtension

    md = markdown.Markdown(
        extensions=[
            TableExtension(),
            FencedCodeExtension(),
            CodeHiliteExtension(css_class="highlight"),
            "md_in_html",
        ]
    )
    return md.convert(content)


def _render_to_html(
    content: str, title: str, metadata: dict[str, Any], template: str = "report"
) -> str:
    """
    Render content to full HTML document using template.

    Args:
        content: Markdown content to render
        title: Report title
        metadata: Extra metadata (date, sources, confidence, etc.)
        template: Template name (report or summary)

    Returns:
        Complete HTML document string
    """
    html_content = _render_markdown_to_html(content)

    # Extract metadata
    sources = metadata.get("sources", ["TAJINE"])
    confidence = metadata.get("confidence", 0)
    mode = metadata.get("mode", "RAPIDE")
    date = metadata.get("date", datetime.now().strftime("%Y-%m-%d %H:%M"))
    territory = metadata.get("territory", "France")

    # Professional PDF template with CSS Paged Media
    html_template = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        /* Page setup for A4 */
        @page {{
            size: A4;
            margin: 2cm 1.5cm;
            @top-center {{
                content: "{title}";
                font-size: 9pt;
                color: #666;
            }}
            @bottom-left {{
                content: "Tawiza - Intelligence Territoriale";
                font-size: 8pt;
                color: #888;
            }}
            @bottom-right {{
                content: "Page " counter(page) " / " counter(pages);
                font-size: 8pt;
                color: #888;
            }}
        }}

        /* Typography */
        body {{
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            font-size: 11pt;
            line-height: 1.5;
            color: #2E3440;
            max-width: 100%;
        }}

        /* Header */
        .header {{
            border-bottom: 2px solid #5E81AC;
            padding-bottom: 1rem;
            margin-bottom: 2rem;
        }}

        .header h1 {{
            color: #2E3440;
            font-size: 24pt;
            font-weight: 600;
            margin: 0 0 0.5rem 0;
        }}

        .header-meta {{
            display: flex;
            gap: 2rem;
            font-size: 10pt;
            color: #4C566A;
        }}

        .header-meta span {{
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
        }}

        /* Content sections */
        h2 {{
            color: #5E81AC;
            font-size: 14pt;
            font-weight: 600;
            border-bottom: 1px solid #D8DEE9;
            padding-bottom: 0.3rem;
            margin-top: 1.5rem;
            margin-bottom: 0.8rem;
            page-break-after: avoid;
        }}

        h3 {{
            color: #4C566A;
            font-size: 12pt;
            font-weight: 600;
            margin-top: 1rem;
            margin-bottom: 0.5rem;
        }}

        p {{
            margin: 0.5rem 0;
            text-align: justify;
        }}

        /* Tables */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1rem 0;
            font-size: 10pt;
        }}

        th {{
            background-color: #ECEFF4;
            color: #2E3440;
            font-weight: 600;
            text-align: left;
            padding: 0.5rem;
            border: 1px solid #D8DEE9;
        }}

        td {{
            padding: 0.5rem;
            border: 1px solid #D8DEE9;
            vertical-align: top;
        }}

        tr:nth-child(even) {{
            background-color: #F8F9FA;
        }}

        /* Lists */
        ul, ol {{
            margin: 0.5rem 0 0.5rem 1.5rem;
            padding: 0;
        }}

        li {{
            margin: 0.3rem 0;
        }}

        /* Code blocks */
        code {{
            font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
            background-color: #ECEFF4;
            padding: 0.1rem 0.3rem;
            border-radius: 3px;
            font-size: 9pt;
        }}

        pre {{
            background-color: #2E3440;
            color: #D8DEE9;
            padding: 1rem;
            border-radius: 5px;
            overflow-x: auto;
            font-size: 9pt;
            margin: 1rem 0;
        }}

        pre code {{
            background: none;
            padding: 0;
            color: inherit;
        }}

        /* Highlight for code */
        .highlight {{
            background-color: #2E3440;
        }}

        /* Footer section */
        .footer {{
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid #D8DEE9;
            font-size: 9pt;
            color: #4C566A;
        }}

        .footer-row {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 0.3rem;
        }}

        /* Confidence badge */
        .confidence-badge {{
            display: inline-block;
            padding: 0.2rem 0.5rem;
            border-radius: 3px;
            font-weight: 600;
            font-size: 9pt;
        }}

        .confidence-high {{
            background-color: #A3BE8C;
            color: white;
        }}

        .confidence-medium {{
            background-color: #EBCB8B;
            color: #2E3440;
        }}

        .confidence-low {{
            background-color: #BF616A;
            color: white;
        }}

        /* Mode badge */
        .mode-badge {{
            display: inline-block;
            padding: 0.2rem 0.5rem;
            background-color: #5E81AC;
            color: white;
            border-radius: 3px;
            font-weight: 600;
            font-size: 9pt;
        }}

        /* Strong/emphasis */
        strong {{
            color: #2E3440;
            font-weight: 600;
        }}

        em {{
            font-style: italic;
        }}

        /* Horizontal rule */
        hr {{
            border: none;
            border-top: 1px solid #D8DEE9;
            margin: 1.5rem 0;
        }}

        /* Page breaks */
        .page-break {{
            page-break-before: always;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
        <div class="header-meta">
            <span>Date: {date}</span>
            <span>Territoire: {territory}</span>
            <span class="mode-badge">{mode}</span>
            <span class="confidence-badge confidence-{"high" if confidence >= 70 else "medium" if confidence >= 40 else "low"}">
                Confiance: {confidence}%
            </span>
        </div>
    </div>

    <div class="content">
        {html_content}
    </div>

    <div class="footer">
        <div class="footer-row">
            <span>Sources: {", ".join(sources)}</span>
            <span>Mode d'analyse: {mode}</span>
        </div>
        <div class="footer-row">
            <span>Genere par Tawiza - Intelligence Territoriale</span>
            <span>{date}</span>
        </div>
    </div>
</body>
</html>"""

    return html_template


@router.post("/pdf", response_class=StreamingResponse)
async def export_pdf(request: ExportRequest) -> StreamingResponse:
    """
    Generate a professional PDF report from conversation content.

    The PDF includes:
    - Header with title, date, territory, and metadata badges
    - Markdown content rendered to styled HTML
    - Tables with professional formatting
    - Code blocks with syntax highlighting
    - Footer with sources and generation info
    - A4 format with page numbers

    Args:
        request: Export request containing content and metadata

    Returns:
        StreamingResponse with PDF file

    Raises:
        HTTPException: If PDF generation fails
    """
    try:
        # Import WeasyPrint here to avoid startup issues if not installed
        from weasyprint import CSS, HTML
        from weasyprint.text.fonts import FontConfiguration

        logger.info(f"Generating PDF for conversation {request.conversation_id}")

        # Build metadata
        metadata = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            **request.metadata,
        }

        # Render HTML
        html_content = _render_to_html(
            content=request.content,
            title=request.title,
            metadata=metadata,
            template=request.format,
        )

        # Configure fonts
        font_config = FontConfiguration()

        # Generate PDF
        html_doc = HTML(string=html_content)
        pdf_bytes = html_doc.write_pdf(font_config=font_config)

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        territory = metadata.get("territory", "france").lower().replace(" ", "-")
        filename = f"tajine-rapport-{territory}-{timestamp}.pdf"

        logger.info(f"PDF generated: {filename} ({len(pdf_bytes)} bytes)")

        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes)),
            },
        )

    except ImportError as e:
        logger.error(f"WeasyPrint not installed: {e}")
        raise HTTPException(
            status_code=500,
            detail="PDF generation not available. WeasyPrint is not installed.",
        )
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate PDF: {str(e)}",
        )


@router.post("/markdown")
async def export_markdown(request: ExportRequest) -> dict[str, Any]:
    """
    Export conversation as formatted Markdown.

    Returns the raw Markdown content with proper formatting.
    This is useful for clients that want to handle rendering themselves.

    Args:
        request: Export request containing content

    Returns:
        Dict with formatted Markdown content
    """
    # Add header and footer to markdown
    date = datetime.now().strftime("%Y-%m-%d %H:%M")
    territory = request.metadata.get("territory", "France")
    sources = request.metadata.get("sources", ["TAJINE"])
    confidence = request.metadata.get("confidence", 0)
    mode = request.metadata.get("mode", "RAPIDE")

    formatted_content = f"""# {request.title}

**Date:** {date}
**Territoire:** {territory}

---

{request.content}

---

*Sources: {", ".join(sources)} | Confiance: {confidence}% | Mode: {mode}*
*Genere par Tawiza - Intelligence Territoriale*
"""

    return {
        "success": True,
        "content": formatted_content,
        "filename": f"tajine-rapport-{date.replace(':', '-').replace(' ', '_')}.md",
    }


@router.get("/formats")
async def list_export_formats() -> dict[str, Any]:
    """
    List available export formats.

    Returns:
        Dict with available formats and their descriptions
    """
    return {
        "formats": [
            {
                "id": "pdf",
                "name": "PDF",
                "description": "Document PDF professionnel avec mise en page A4",
                "mime_type": "application/pdf",
                "endpoint": "/api/v1/export/pdf",
            },
            {
                "id": "markdown",
                "name": "Markdown",
                "description": "Texte Markdown formaté pour copie ou traitement",
                "mime_type": "text/markdown",
                "endpoint": "/api/v1/export/markdown",
            },
        ],
    }
