"""
LLM Contextualizer - Generates human-readable descriptions of detected anomalies.

Uses Ollama (local LLM) to transform raw cross-source detections into
actionable intelligence reports in French.
"""

import httpx
from loguru import logger

# Default Ollama endpoint
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_MODEL = "qwen2.5:7b"  # Faster for contextualisation, use qwen3.5:27b for quality


SYSTEM_PROMPT = """Tu es un analyste en intelligence territoriale française.
Tu reçois des données de détection automatique de micro-signaux territoriaux.
Ton rôle est de produire une analyse concise et actionnable en français.

Règles:
- Maximum 3 phrases
- Cite les sources de données (SIRENE, France Travail, presse locale)
- Mentionne le département et les chiffres clés
- Donne une interprétation économique
- Suggère une action ou un point d'attention
- Pas de jargon technique sur les z-scores"""


def _build_prompt(
    signal_type: str,
    code_dept: str,
    sources: list[str],
    metrics: dict[str, float],
    extra_context: str = "",
) -> str:
    """Build a contextualisation prompt from detection data."""

    source_names = {
        "sirene": "SIRENE (créations/fermetures d'entreprises)",
        "france_travail": "France Travail (offres d'emploi)",
        "presse_locale": "Presse locale (articles)",
    }

    type_descriptions = {
        "dynamisme_territorial": "DYNAMISME TERRITORIAL - convergence de signaux positifs",
        "declin_territorial": "DÉCLIN TERRITORIAL - convergence de signaux négatifs",
        "tension_emploi": "TENSION SUR L'EMPLOI - forte demande non satisfaite",
        "crise_sectorielle": "CRISE SECTORIELLE - cluster de fermetures et licenciements",
        "attractivite": "ATTRACTIVITÉ CROISSANTE - investissements et constructions",
        "desertification": "DÉSERTIFICATION - services en recul",
    }

    sources_text = ", ".join(source_names.get(s, s) for s in sources)
    metrics_text = "\n".join(
        f"  - {m}: z-score = {z:.1f} ({'hausse' if z > 0 else 'baisse'} significative)"
        for m, z in metrics.items()
    )

    prompt = f"""Analyse ce micro-signal territorial détecté automatiquement:

TYPE: {type_descriptions.get(signal_type, signal_type)}
DÉPARTEMENT: {code_dept}
SOURCES CONVERGENTES: {sources_text}
MÉTRIQUES:
{metrics_text}

{f"CONTEXTE SUPPLÉMENTAIRE: {extra_context}" if extra_context else ""}

Produis une analyse concise (3 phrases max) pour un décideur territorial."""

    return prompt


async def contextualize_signal(
    signal_type: str,
    code_dept: str,
    sources: list[str],
    metrics: dict[str, float],
    extra_context: str = "",
    model: str = DEFAULT_MODEL,
    ollama_url: str = OLLAMA_URL,
    timeout: float = 180.0,
) -> str:
    """
    Generate a contextualised description of a detected micro-signal.

    Returns a French-language analysis string.
    """
    prompt = _build_prompt(signal_type, code_dept, sources, metrics, extra_context)

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                ollama_url,
                json={
                    "model": model,
                    "prompt": prompt,
                    "system": SYSTEM_PROMPT,
                    "stream": False,
                    "options": {
                        "num_predict": 100,  # ~2-3 sentences
                        "temperature": 0.3,  # factual, not creative
                        "num_ctx": 1024,  # smaller context for speed
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            text = data.get("response", "").strip()

            # Clean up thinking tags if present (qwen3)
            if "<think>" in text:
                import re

                text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

            logger.info(
                f"[contextualizer] Generated analysis for {signal_type} "
                f"dept={code_dept} ({len(text)} chars, "
                f"{data.get('eval_count', 0)} tokens)"
            )
            return text

    except httpx.TimeoutException:
        logger.warning(f"[contextualizer] Timeout for {signal_type} dept={code_dept}")
        return f"Analyse non disponible (timeout LLM) pour le signal {signal_type} dans le département {code_dept}."
    except Exception as e:
        logger.error(f"[contextualizer] Error: {e}")
        return f"Analyse non disponible pour le département {code_dept}."


async def contextualize_batch(
    signals: list[dict],
    model: str = DEFAULT_MODEL,
    ollama_url: str = OLLAMA_URL,
) -> list[dict]:
    """
    Contextualize a batch of micro-signals.

    Each signal dict must have: signal_type, code_dept, sources, metrics
    Returns the same dicts with 'description' field updated.
    """
    for signal in signals:
        description = await contextualize_signal(
            signal_type=signal["signal_type"],
            code_dept=signal["code_dept"],
            sources=signal["sources"],
            metrics=signal["metrics"],
            model=model,
            ollama_url=ollama_url,
        )
        signal["description"] = description

    return signals
