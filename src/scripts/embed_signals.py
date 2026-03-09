#!/usr/bin/env python3
"""Embed signals into pgvector for semantic search.

Uses nomic-embed-text via Ollama to generate 768-dim embeddings.
Processes signals in batches, skipping already-embedded ones.
"""

import asyncio
import os
import sys
from pathlib import Path

import asyncpg
import httpx
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

DB_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5433/tawiza")
OLLAMA_URL = "http://localhost:11434"
EMBED_MODEL = "nomic-embed-text"
BATCH_SIZE = 50  # signals per batch
EMBED_BATCH = 10  # embeddings per Ollama call


def build_signal_text(row: asyncpg.Record) -> str:
    """Build a searchable text from a signal row."""
    parts = []
    
    source = row["source"] or ""
    parts.append(f"Source: {source}")
    
    if row.get("code_dept"):
        parts.append(f"Departement: {row['code_dept']}")
    
    if row.get("metric_name"):
        parts.append(f"Metrique: {row['metric_name']}")
    
    if row.get("metric_value") is not None:
        parts.append(f"Valeur: {row['metric_value']}")
    
    if row.get("signal_type"):
        parts.append(f"Type: {row['signal_type']}")
    
    if row.get("event_date"):
        parts.append(f"Date: {row['event_date']}")
    
    if row.get("extracted_text"):
        text = str(row["extracted_text"])[:300]
        parts.append(f"Contenu: {text}")
    elif row.get("raw_data"):
        # Extract key fields from raw_data JSON
        import json
        try:
            raw = json.loads(row["raw_data"]) if isinstance(row["raw_data"], str) else row["raw_data"]
            for key in ["denomination", "nom_raison_sociale", "intitule", "titre", "description", "libelle"]:
                if key in raw and raw[key]:
                    parts.append(f"{key}: {str(raw[key])[:200]}")
                    break
        except (json.JSONDecodeError, TypeError):
            pass
    
    return " | ".join(parts)


async def embed_texts(client: httpx.AsyncClient, texts: list[str]) -> list[list[float]]:
    """Get embeddings from Ollama nomic-embed-text."""
    embeddings = []
    for text in texts:
        try:
            resp = await client.post(
                f"{OLLAMA_URL}/api/embed",
                json={"model": EMBED_MODEL, "input": text},
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            # Ollama returns {"embeddings": [[...]]}
            emb = data.get("embeddings", [[]])[0]
            if len(emb) == 768:
                embeddings.append(emb)
            else:
                logger.warning(f"Wrong embedding dim: {len(emb)}")
                embeddings.append(None)
        except Exception as e:
            logger.warning(f"Embed error: {e}")
            embeddings.append(None)
    return embeddings


async def run_embedding(limit: int = 50000):
    """Main embedding pipeline."""
    conn = await asyncpg.connect(DB_URL)
    
    try:
        # Count already embedded
        existing = await conn.fetchval("SELECT count(*) FROM signal_embeddings")
        total = await conn.fetchval("SELECT count(*) FROM signals")
        remaining = total - existing
        logger.info(f"Signals: {total} total, {existing} embedded, {remaining} remaining")
        
        if remaining == 0:
            logger.info("All signals already embedded!")
            return
        
        # Process in batches
        processed = 0
        async with httpx.AsyncClient() as client:
            while processed < limit:
                # Get unembedded signals
                rows = await conn.fetch("""
                    SELECT s.id, s.source, s.code_dept, s.metric_name, s.metric_value,
                           s.signal_type, s.event_date, s.extracted_text, s.raw_data
                    FROM signals s
                    LEFT JOIN signal_embeddings se ON s.id = se.signal_id
                    WHERE se.id IS NULL
                    ORDER BY s.id
                    LIMIT $1
                """, BATCH_SIZE)
                
                if not rows:
                    break
                
                # Build texts
                texts = []
                signal_ids = []
                for row in rows:
                    text = build_signal_text(row)
                    if text and len(text) > 10:
                        texts.append(text)
                        signal_ids.append(row["id"])
                
                if not texts:
                    break
                
                # Get embeddings
                embeddings = await embed_texts(client, texts)
                
                # Insert into DB
                inserted = 0
                for sid, text, emb in zip(signal_ids, texts, embeddings):
                    if emb is not None:
                        try:
                            await conn.execute("""
                                INSERT INTO signal_embeddings (signal_id, embedding, text_content)
                                VALUES ($1, $2, $3)
                                ON CONFLICT (signal_id) DO NOTHING
                            """, sid, str(emb), text)
                            inserted += 1
                        except Exception as e:
                            logger.warning(f"Insert error for signal {sid}: {e}")
                
                processed += len(rows)
                logger.info(f"Batch done: {inserted}/{len(rows)} embedded (total: {processed})")
        
        final = await conn.fetchval("SELECT count(*) FROM signal_embeddings")
        logger.info(f"Embedding complete: {final} total embeddings")
        
    finally:
        await conn.close()


async def search_similar(query: str, limit: int = 10) -> list[dict]:
    """Semantic search: find signals similar to a query."""
    async with httpx.AsyncClient() as client:
        # Embed the query
        resp = await client.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": EMBED_MODEL, "input": query},
            timeout=30.0,
        )
        resp.raise_for_status()
        query_emb = resp.json()["embeddings"][0]
    
    conn = await asyncpg.connect(DB_URL)
    try:
        rows = await conn.fetch("""
            SELECT se.signal_id, se.text_content,
                   1 - (se.embedding <=> $1::vector) as similarity,
                   s.source, s.code_dept, s.event_date, s.metric_name, s.metric_value
            FROM signal_embeddings se
            JOIN signals s ON s.id = se.signal_id
            ORDER BY se.embedding <=> $1::vector
            LIMIT $2
        """, str(query_emb), limit)
        
        return [dict(r) for r in rows]
    finally:
        await conn.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50000)
    parser.add_argument("--search", type=str, default=None)
    args = parser.parse_args()
    
    if args.search:
        results = asyncio.run(search_similar(args.search))
        for r in results:
            print(f"[{r['similarity']:.3f}] {r['source']} dept={r['code_dept']} "
                  f"{r['event_date']} | {r['text_content'][:100]}")
    else:
        asyncio.run(run_embedding(limit=args.limit))
