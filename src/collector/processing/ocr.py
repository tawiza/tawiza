"""OCR processing using GLM-OCR via Ollama for document analysis.

Extracts structured text from:
- PDF scans (BODACC publications, financial reports)
- Screenshots (anti-bot pages, LeBonCoin)
- Building permits, legal documents
- Any image containing French text

Uses glm-ocr model via Ollama API for high-quality OCR with layout understanding.
"""

import base64
import json
from pathlib import Path
from typing import Any

import httpx
from loguru import logger

# Ollama endpoint
OLLAMA_BASE = "http://localhost:11434"
OCR_MODEL = "glm-ocr"
VISION_MODEL = "qwen3-vl:8b"  # Fallback if glm-ocr unavailable


async def extract_text_from_image(
    image_path: str | Path,
    prompt: str = "Extract all text from this image. Return the text exactly as it appears, preserving layout and structure.",
    model: str | None = None,
) -> dict[str, Any]:
    """
    Extract text from an image using GLM-OCR or vision model.

    Args:
        image_path: Path to image file (PNG, JPG, PDF page screenshot)
        prompt: OCR instruction prompt
        model: Model override (default: glm-ocr, fallback: qwen3-vl:8b)

    Returns:
        {
            "text": extracted text,
            "model": model used,
            "success": bool,
            "error": optional error message,
        }
    """
    path = Path(image_path)
    if not path.exists():
        return {"text": "", "model": "", "success": False, "error": f"File not found: {path}"}

    # Read and encode image
    image_data = path.read_bytes()
    image_b64 = base64.b64encode(image_data).decode("utf-8")

    # Try glm-ocr first, fallback to vision model
    models_to_try = [model] if model else [OCR_MODEL, VISION_MODEL]

    for m in models_to_try:
        try:
            result = await _call_ollama_vision(m, prompt, image_b64)
            if result["success"]:
                return result
        except Exception as e:
            logger.debug(f"[ocr] Model {m} failed: {e}")
            continue

    return {"text": "", "model": "", "success": False, "error": "All models failed"}


async def extract_text_from_bytes(
    image_bytes: bytes,
    prompt: str = "Extract all text from this image.",
    model: str | None = None,
) -> dict[str, Any]:
    """Extract text from raw image bytes."""
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    models_to_try = [model] if model else [OCR_MODEL, VISION_MODEL]

    for m in models_to_try:
        try:
            result = await _call_ollama_vision(m, prompt, image_b64)
            if result["success"]:
                return result
        except Exception as e:
            logger.debug(f"[ocr] Model {m} failed: {e}")
            continue

    return {"text": "", "model": "", "success": False, "error": "All models failed"}


async def analyze_document(
    image_path: str | Path,
    doc_type: str = "general",
) -> dict[str, Any]:
    """
    Analyze a document image with type-specific prompts.

    Args:
        image_path: Path to document image
        doc_type: One of 'bodacc', 'financial', 'permit', 'leboncoin', 'general'

    Returns:
        Structured extraction result
    """
    prompts = {
        "bodacc": (
            "This is a BODACC (Bulletin officiel des annonces civiles et commerciales) document. "
            "Extract: company name (raison sociale), SIREN/SIRET number, type of event "
            "(creation, modification, radiation, liquidation, sauvegarde), date, "
            "registered address, and any financial amounts mentioned. "
            "Return as structured JSON."
        ),
        "financial": (
            "This is a French financial document (bilan, compte de résultat). "
            "Extract: company name, SIREN, fiscal year, total revenue (chiffre d'affaires), "
            "net result (résultat net), total assets (total bilan), equity (capitaux propres). "
            "Return as structured JSON with numeric values."
        ),
        "permit": (
            "This is a French building permit (permis de construire). "
            "Extract: permit number, applicant name, location (commune, address), "
            "project type (construction, renovation, demolition), surface area, "
            "and decision (granted/refused/pending). Return as structured JSON."
        ),
        "leboncoin": (
            "This is a LeBonCoin listing. Extract: title, price, location (city, postal code), "
            "category, description text, and any indicators of business closure "
            "(cessation, liquidation, fermeture). Return as structured JSON."
        ),
        "general": (
            "Extract all text from this document image. Preserve the structure and layout. "
            "Identify key information: dates, names, numbers, addresses."
        ),
    }

    prompt = prompts.get(doc_type, prompts["general"])
    result = await extract_text_from_image(image_path, prompt)

    if result["success"] and doc_type != "general":
        # Try to parse JSON from the response
        try:
            parsed = _extract_json(result["text"])
            if parsed:
                result["structured"] = parsed
        except Exception:
            pass

    result["doc_type"] = doc_type
    return result


async def ocr_screenshot(
    url: str,
    playwright_page=None,
    prompt: str = "Extract all visible text from this webpage screenshot.",
) -> dict[str, Any]:
    """
    Take a screenshot of a page and OCR it.
    Useful for anti-bot pages that block text extraction.

    Args:
        url: URL (for logging)
        playwright_page: An active Playwright page object
        prompt: OCR prompt

    Returns:
        OCR result with extracted text
    """
    if playwright_page is None:
        return {"text": "", "success": False, "error": "No playwright page provided"}

    try:
        screenshot = await playwright_page.screenshot(full_page=False)
        result = await extract_text_from_bytes(screenshot, prompt)
        result["source_url"] = url
        return result
    except Exception as e:
        return {"text": "", "success": False, "error": str(e), "source_url": url}


async def _call_ollama_vision(
    model: str, prompt: str, image_b64: str
) -> dict[str, Any]:
    """Call Ollama vision API."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{OLLAMA_BASE}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "images": [image_b64],
                "stream": False,
                "options": {"num_predict": 2048},
            },
        )
        resp.raise_for_status()
        data = resp.json()

        return {
            "text": data.get("response", ""),
            "model": model,
            "success": True,
            "eval_count": data.get("eval_count", 0),
            "eval_duration_ms": (data.get("eval_duration", 0)) / 1e6,
        }


def _extract_json(text: str) -> dict | list | None:
    """Try to extract JSON from LLM response text."""
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON block in markdown
    for marker in ["```json", "```"]:
        if marker in text:
            start = text.index(marker) + len(marker)
            end = text.index("```", start) if "```" in text[start:] else len(text)
            try:
                return json.loads(text[start:end].strip())
            except (json.JSONDecodeError, ValueError):
                pass

    return None


async def check_ocr_available() -> dict[str, bool]:
    """Check which OCR models are available."""
    result = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get(f"{OLLAMA_BASE}/api/tags")
            models = [m["name"] for m in resp.json().get("models", [])]
            result["glm-ocr"] = any("glm-ocr" in m for m in models)
            result["qwen3-vl"] = any("qwen3-vl" in m for m in models)
            result["available"] = result["glm-ocr"] or result["qwen3-vl"]
        except Exception:
            result["available"] = False
    return result
