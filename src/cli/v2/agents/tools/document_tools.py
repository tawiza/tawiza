"""Document extraction and analysis tools.

Extracts structured information from PDFs and web pages:
- Text extraction from PDF/HTML
- Entity extraction (organizations, amounts, dates)
- Document summarization
"""

import re
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

from src.cli.v2.agents.unified.tools import Tool, ToolCategory, ToolRegistry


def _extract_text_from_html(html: str, max_length: int = 10000) -> str:
    """Extract readable text from HTML."""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")

        # Remove noise elements
        for element in soup(
            ["script", "style", "nav", "footer", "header", "aside", "iframe", "noscript"]
        ):
            element.decompose()

        # Get text
        text = soup.get_text(separator="\n", strip=True)

        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = "\n".join(lines)

        if len(text) > max_length:
            text = text[:max_length] + "..."

        return text
    except Exception as e:
        logger.warning(f"HTML extraction failed: {e}")
        return html[:max_length] if len(html) > max_length else html


def _extract_text_from_pdf(pdf_path: str, max_pages: int = 50) -> str:
    """Extract text from PDF file."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(pdf_path)
        text_parts = []

        for page_num in range(min(len(doc), max_pages)):
            page = doc[page_num]
            text_parts.append(f"--- Page {page_num + 1} ---\n{page.get_text()}")

        doc.close()
        return "\n\n".join(text_parts)
    except ImportError:
        logger.warning("PyMuPDF not installed, falling back to basic extraction")
        # Fallback: try pdfplumber or pypdf
        try:
            import pypdf

            reader = pypdf.PdfReader(pdf_path)
            text_parts = []
            for i, page in enumerate(reader.pages[:max_pages]):
                text_parts.append(f"--- Page {i + 1} ---\n{page.extract_text() or ''}")
            return "\n\n".join(text_parts)
        except ImportError:
            return "[PDF extraction requires PyMuPDF or pypdf: pip install pymupdf]"
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        return f"[PDF extraction error: {e}]"


def _extract_entities(text: str) -> dict[str, list[str]]:
    """Extract entities from text using regex patterns."""
    entities = {
        "montants": [],
        "dates": [],
        "emails": [],
        "sirets": [],
        "urls": [],
        "organisations": [],
    }

    # Amounts (€, euros, EUR)
    montant_patterns = [
        r"(\d[\d\s]*(?:[.,]\d+)?\s*(?:€|euros?|EUR|M€|k€))",
        r"(\d[\d\s]*(?:[.,]\d+)?\s*millions?\s*d\'euros)",
        r"(\d[\d\s]*(?:[.,]\d+)?\s*milliards?\s*d\'euros)",
    ]
    for pattern in montant_patterns:
        entities["montants"].extend(re.findall(pattern, text, re.IGNORECASE))

    # Dates
    date_patterns = [
        r"\b(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4})\b",
        r"\b(\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4})\b",
    ]
    for pattern in date_patterns:
        entities["dates"].extend(re.findall(pattern, text, re.IGNORECASE))

    # Emails
    entities["emails"] = re.findall(r"\b[\w.-]+@[\w.-]+\.\w+\b", text)

    # SIRET (14 digits)
    entities["sirets"] = re.findall(r"\b(\d{3}\s?\d{3}\s?\d{3}\s?\d{5})\b", text)

    # URLs
    entities["urls"] = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', text)

    # Clean and deduplicate
    for key in entities:
        entities[key] = list(set(entities[key]))[:20]  # Limit to 20 per type

    return entities


def _extract_organizations(text: str) -> list[str]:
    """Extract organization names from text using heuristics."""
    orgs = []

    # Common patterns for French organizations
    patterns = [
        r"(?:la\s+)?(?:société|entreprise|groupe|association|fondation|institut|laboratoire|pôle|cluster)\s+([A-Z][A-Za-zÀ-ÿ\s\-&]+)",
        r"([A-Z][A-Z0-9\s\-&]{2,}(?:\s+(?:SAS|SA|SARL|SNC|EURL|SASU))?)",  # Acronyms/company names
        r"(?:Université|CNRS|INRIA|CEA|INSERM|Ifremer)\s+(?:de\s+)?([A-Za-zÀ-ÿ\s\-]+)",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        orgs.extend(matches)

    # Clean and deduplicate
    orgs = [org.strip() for org in orgs if len(org.strip()) > 3]
    return list(set(orgs))[:30]


def register_document_tools(registry: ToolRegistry) -> None:
    """Register document extraction and analysis tools."""

    async def doc_extract(url_or_path: str) -> dict[str, Any]:
        """Extract text content from a URL or local file path.

        Args:
            url_or_path: URL (http/https) or local file path (PDF, HTML, TXT)

        Returns:
            Dict with extracted text and metadata
        """
        try:
            text = ""
            source_type = ""
            title = ""

            # Check if URL or file path
            if url_or_path.startswith(("http://", "https://")):
                source_type = "url"

                async with httpx.AsyncClient(timeout=30.0) as client:
                    headers = {"User-Agent": "Mozilla/5.0 (compatible; DocumentBot/1.0)"}
                    response = await client.get(url_or_path, headers=headers, follow_redirects=True)
                    response.raise_for_status()

                    content_type = response.headers.get("content-type", "")

                    if "pdf" in content_type:
                        # Download PDF to temp file
                        import tempfile

                        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                            f.write(response.content)
                            temp_path = f.name
                        text = _extract_text_from_pdf(temp_path)
                        Path(temp_path).unlink()  # Clean up
                        source_type = "pdf"
                    else:
                        # HTML
                        text = _extract_text_from_html(response.text)
                        # Try to get title
                        try:
                            from bs4 import BeautifulSoup

                            soup = BeautifulSoup(response.text, "html.parser")
                            title_tag = soup.find("title")
                            if title_tag:
                                title = title_tag.get_text(strip=True)
                        except Exception:
                            pass

            else:
                # Local file
                path = Path(url_or_path)
                if not path.exists():
                    return {"success": False, "error": f"File not found: {url_or_path}"}

                suffix = path.suffix.lower()

                if suffix == ".pdf":
                    text = _extract_text_from_pdf(str(path))
                    source_type = "pdf"
                    title = path.stem
                elif suffix in [".html", ".htm"]:
                    text = _extract_text_from_html(
                        path.read_text(encoding="utf-8", errors="ignore")
                    )
                    source_type = "html"
                elif suffix in [".txt", ".md", ".csv"]:
                    text = path.read_text(encoding="utf-8", errors="ignore")[:50000]
                    source_type = suffix[1:]
                else:
                    return {"success": False, "error": f"Unsupported file type: {suffix}"}

            return {
                "success": True,
                "source": url_or_path,
                "source_type": source_type,
                "title": title,
                "text": text,
                "length": len(text),
                "word_count": len(text.split()),
            }

        except httpx.HTTPStatusError as e:
            return {"success": False, "error": f"HTTP error: {e.response.status_code}"}
        except Exception as e:
            logger.error(f"Document extraction failed: {e}")
            return {"success": False, "error": str(e)}

    async def doc_analyze(content: str) -> dict[str, Any]:
        """Analyze document content and extract structured entities.

        Args:
            content: Text content to analyze

        Returns:
            Dict with extracted entities (amounts, dates, organizations, etc.)
        """
        try:
            if not content or len(content) < 10:
                return {"success": False, "error": "Content too short to analyze"}

            # Extract entities
            entities = _extract_entities(content)
            organizations = _extract_organizations(content)

            # Basic statistics
            word_count = len(content.split())
            line_count = len(content.splitlines())

            return {
                "success": True,
                "statistics": {
                    "word_count": word_count,
                    "line_count": line_count,
                    "char_count": len(content),
                },
                "entities": {
                    "montants": entities["montants"][:10],
                    "dates": entities["dates"][:10],
                    "sirets": entities["sirets"][:10],
                    "emails": entities["emails"][:10],
                    "urls": entities["urls"][:10],
                },
                "organizations": organizations[:20],
            }

        except Exception as e:
            logger.error(f"Document analysis failed: {e}")
            return {"success": False, "error": str(e)}

    async def doc_summarize(
        content: str, focus: str | None = None, max_length: int = 500
    ) -> dict[str, Any]:
        """Create a summary of document content.

        Note: For LLM-based summarization, use the agent's thinking capability.
        This tool provides extractive summarization based on key sentences.

        Args:
            content: Text content to summarize
            focus: Optional focus area (e.g., "financier", "acteurs", "dates")
            max_length: Maximum summary length in characters

        Returns:
            Dict with summary and key points
        """
        try:
            if not content or len(content) < 100:
                return {"success": False, "error": "Content too short to summarize"}

            # Split into sentences
            sentences = re.split(r"[.!?]+", content)
            sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

            if not sentences:
                return {"success": False, "error": "No valid sentences found"}

            # Score sentences by importance
            scored = []
            for sent in sentences:
                score = 0

                # Length bonus (not too short, not too long)
                if 50 < len(sent) < 200:
                    score += 1

                # Contains numbers (often important)
                if re.search(r"\d", sent):
                    score += 1

                # Contains key terms
                key_terms = [
                    "important",
                    "objectif",
                    "résultat",
                    "montant",
                    "projet",
                    "million",
                    "euro",
                ]
                if any(term in sent.lower() for term in key_terms):
                    score += 2

                # Focus filtering
                if focus:
                    focus_lower = focus.lower()
                    if focus_lower in ["financier", "budget", "montant"]:
                        if re.search(r"(?:€|euro|million|budget|financement)", sent, re.IGNORECASE):
                            score += 3
                    elif focus_lower in ["acteur", "entreprise", "partenaire"]:
                        if re.search(
                            r"(?:société|entreprise|partenaire|consortium)", sent, re.IGNORECASE
                        ):
                            score += 3
                    elif focus_lower in ["date", "calendrier", "délai"]:
                        if re.search(
                            r"(?:\d{4}|janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)",
                            sent,
                            re.IGNORECASE,
                        ):
                            score += 3

                scored.append((score, sent))

            # Sort by score and take top sentences
            scored.sort(reverse=True, key=lambda x: x[0])

            summary_parts = []
            current_length = 0

            for score, sent in scored:
                if current_length + len(sent) > max_length:
                    break
                summary_parts.append(sent)
                current_length += len(sent)

            summary = ". ".join(summary_parts)
            if summary and not summary.endswith("."):
                summary += "."

            return {
                "success": True,
                "summary": summary,
                "focus": focus,
                "original_length": len(content),
                "summary_length": len(summary),
                "compression_ratio": round(len(summary) / len(content) * 100, 1),
            }

        except Exception as e:
            logger.error(f"Document summarization failed: {e}")
            return {"success": False, "error": str(e)}

    async def doc_search_in_text(content: str, query: str) -> dict[str, Any]:
        """Search for specific information in document content.

        Args:
            content: Text content to search in
            query: Search query (keywords or regex pattern)

        Returns:
            Dict with matching excerpts and their positions
        """
        try:
            matches = []
            query_lower = query.lower()
            content_lower = content.lower()

            # Find all occurrences
            start = 0
            while True:
                pos = content_lower.find(query_lower, start)
                if pos == -1:
                    break

                # Extract context (100 chars before and after)
                context_start = max(0, pos - 100)
                context_end = min(len(content), pos + len(query) + 100)
                excerpt = content[context_start:context_end]

                # Clean up excerpt
                if context_start > 0:
                    excerpt = "..." + excerpt
                if context_end < len(content):
                    excerpt = excerpt + "..."

                matches.append(
                    {
                        "position": pos,
                        "excerpt": excerpt.replace("\n", " "),
                    }
                )

                start = pos + 1

                if len(matches) >= 20:  # Limit results
                    break

            return {
                "success": True,
                "query": query,
                "match_count": len(matches),
                "matches": matches,
            }

        except Exception as e:
            logger.error(f"Document search failed: {e}")
            return {"success": False, "error": str(e)}

    # Register tools
    registry._tools["doc.extract"] = Tool(
        name="doc.extract",
        func=doc_extract,
        category=ToolCategory.DOCUMENT,
        description="Extract text from URL or file (PDF, HTML, TXT). Returns clean text content.",
    )

    registry._tools["doc.analyze"] = Tool(
        name="doc.analyze",
        func=doc_analyze,
        category=ToolCategory.DOCUMENT,
        description="Analyze text to extract entities: amounts, dates, SIRETs, organizations.",
    )

    registry._tools["doc.summarize"] = Tool(
        name="doc.summarize",
        func=doc_summarize,
        category=ToolCategory.DOCUMENT,
        description="Create extractive summary. Optional focus: 'financier', 'acteurs', 'dates'.",
    )

    registry._tools["doc.search"] = Tool(
        name="doc.search",
        func=doc_search_in_text,
        category=ToolCategory.DOCUMENT,
        description="Search for keywords in document text. Returns matching excerpts with context.",
    )

    logger.debug("Registered 4 document tools")
