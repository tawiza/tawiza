"""RAG (Retrieval-Augmented Generation) for TAJINE.

Semantic search over signal embeddings + context formatting with citations.
"""

import os
from typing import Any

import asyncpg
import httpx
from loguru import logger

OLLAMA_URL = os.getenv("OLLAMA_HOST", "http://localhost:11434")
EMBED_MODEL = "nomic-embed-text"

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Get or create connection pool."""
    global _pool
    if _pool is None or _pool._closed:
        db_url = os.getenv(
            "COLLECTOR_DATABASE_URL", "postgresql://localhost:5433/tawiza"
        )
        db_url = db_url.replace("postgresql+asyncpg://", "postgres://").replace(
            "postgresql://", "postgres://"
        )
        _pool = await asyncpg.create_pool(db_url, min_size=2, max_size=5, timeout=10)
    return _pool


async def embed_query(query: str) -> list[float] | None:
    """Embed a query string using nomic-embed-text."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{OLLAMA_URL}/api/embed",
                json={"model": EMBED_MODEL, "input": query},
            )
            resp.raise_for_status()
            embs = resp.json().get("embeddings", [[]])
            if embs and len(embs[0]) == 768:
                return embs[0]
    except Exception as e:
        logger.warning(f"RAG embed_query error: {e}")
    return None


async def search_signals(
    query: str,
    limit: int = 10,
    department: str | None = None,
    min_similarity: float = 0.3,
) -> list[dict[str, Any]]:
    """Semantic search: find signals most relevant to a query.

    Returns signals with similarity score, ready for LLM context injection.
    """
    query_emb = await embed_query(query)
    if query_emb is None:
        logger.warning("RAG: could not embed query, falling back to empty results")
        return []

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Build query with optional department filter
        if department:
            rows = await conn.fetch(
                """
                SELECT se.signal_id, se.text_content,
                       1 - (se.embedding <=> $1::vector) as similarity,
                       s.source, s.code_dept, s.event_date, s.metric_name,
                       s.metric_value, s.signal_type, s.extracted_text
                FROM signal_embeddings se
                JOIN signals s ON s.id = se.signal_id
                WHERE s.code_dept = $3
                ORDER BY se.embedding <=> $1::vector
                LIMIT $2
            """,
                str(query_emb),
                limit,
                department,
            )
        else:
            rows = await conn.fetch(
                """
                SELECT se.signal_id, se.text_content,
                       1 - (se.embedding <=> $1::vector) as similarity,
                       s.source, s.code_dept, s.event_date, s.metric_name,
                       s.metric_value, s.signal_type, s.extracted_text
                FROM signal_embeddings se
                JOIN signals s ON s.id = se.signal_id
                ORDER BY se.embedding <=> $1::vector
                LIMIT $2
            """,
                str(query_emb),
                limit,
            )

    results = []
    for r in rows:
        sim = float(r["similarity"])
        if sim < min_similarity:
            continue
        results.append(
            {
                "signal_id": r["signal_id"],
                "similarity": round(sim, 3),
                "source": r["source"],
                "department": r["code_dept"],
                "date": str(r["event_date"]) if r["event_date"] else None,
                "metric": r["metric_name"],
                "value": float(r["metric_value"]) if r["metric_value"] is not None else None,
                "type": r["signal_type"],
                "text": (r["extracted_text"] or r["text_content"] or "")[:200],
            }
        )

    logger.info(
        f"RAG search: query='{query[:60]}' dept={department} → {len(results)} results (top sim={results[0]['similarity'] if results else 0})"
    )
    return results


def format_rag_context(results: list[dict[str, Any]], max_chars: int = 3000) -> str:
    """Format RAG results as context for the LLM prompt.

    Each signal includes its ID for citation.
    """
    if not results:
        return ""

    lines = ["SIGNAUX PERTINENTS (cite les IDs [SIG-xxx] dans ta reponse):"]
    total = len(lines[0])

    for r in results:
        parts = [f"[SIG-{r['signal_id']}]"]
        parts.append(f"({r['source']}")
        if r["department"]:
            parts.append(f"dept {r['department']}")
        if r["date"]:
            parts.append(f"{r['date']}")
        parts_str = " ".join(parts) + ")"

        if r["metric"] and r["value"] is not None:
            parts_str += f" {r['metric']}={r['value']}"
        if r["text"]:
            parts_str += f" | {r['text'][:150]}"

        line = f"  - {parts_str}"
        if total + len(line) > max_chars:
            break
        lines.append(line)
        total += len(line)

    return "\n".join(lines)


async def build_rag_context(
    query: str,
    department: str | None = None,
    top_k: int = 15,
    max_chars: int = 3000,
) -> str:
    """Full RAG pipeline: embed query → search → format context.

    Returns formatted string ready to inject into LLM prompt.
    """
    results = await search_signals(query, limit=top_k, department=department)
    return format_rag_context(results, max_chars=max_chars)
