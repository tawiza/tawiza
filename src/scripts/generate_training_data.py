#!/usr/bin/env python3
"""Generate synthetic training data from real signals for TAJINE fine-tuning.

Creates question/answer pairs about territorial intelligence from actual DB data.
Output: JSONL file compatible with Ollama fine-tuning (SFT format).

Usage:
    python3 src/scripts/generate_training_data.py [--count 500] [--output training_data.jsonl]
"""

import asyncio
import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path

import asyncpg
import httpx
from loguru import logger

DB_DSN = os.getenv(
    "COLLECTOR_DATABASE_URL",
    "postgresql://localhost:5433/tawiza",
).replace("+asyncpg", "")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = "qwen3.5:27b"

# Department names for readable output
DEPT_NAMES = {
    "01": "Ain", "02": "Aisne", "03": "Allier", "04": "Alpes-de-Haute-Provence",
    "05": "Hautes-Alpes", "06": "Alpes-Maritimes", "07": "Ardeche", "08": "Ardennes",
    "09": "Ariege", "10": "Aube", "11": "Aude", "12": "Aveyron",
    "13": "Bouches-du-Rhone", "14": "Calvados", "15": "Cantal", "16": "Charente",
    "17": "Charente-Maritime", "18": "Cher", "19": "Correze", "2A": "Corse-du-Sud",
    "2B": "Haute-Corse", "21": "Cote-d'Or", "22": "Cotes-d'Armor", "23": "Creuse",
    "24": "Dordogne", "25": "Doubs", "26": "Drome", "27": "Eure",
    "28": "Eure-et-Loir", "29": "Finistere", "30": "Gard", "31": "Haute-Garonne",
    "32": "Gers", "33": "Gironde", "34": "Herault", "35": "Ille-et-Vilaine",
    "36": "Indre", "37": "Indre-et-Loire", "38": "Isere", "39": "Jura",
    "40": "Landes", "41": "Loir-et-Cher", "42": "Loire", "43": "Haute-Loire",
    "44": "Loire-Atlantique", "45": "Loiret", "46": "Lot", "47": "Lot-et-Garonne",
    "48": "Lozere", "49": "Maine-et-Loire", "50": "Manche", "51": "Marne",
    "52": "Haute-Marne", "53": "Mayenne", "54": "Meurthe-et-Moselle", "55": "Meuse",
    "56": "Morbihan", "57": "Moselle", "58": "Nievre", "59": "Nord",
    "60": "Oise", "61": "Orne", "62": "Pas-de-Calais", "63": "Puy-de-Dome",
    "64": "Pyrenees-Atlantiques", "65": "Hautes-Pyrenees", "66": "Pyrenees-Orientales",
    "67": "Bas-Rhin", "68": "Haut-Rhin", "69": "Rhone", "70": "Haute-Saone",
    "71": "Saone-et-Loire", "72": "Sarthe", "73": "Savoie", "74": "Haute-Savoie",
    "75": "Paris", "76": "Seine-Maritime", "77": "Seine-et-Marne", "78": "Yvelines",
    "79": "Deux-Sevres", "80": "Somme", "81": "Tarn", "82": "Tarn-et-Garonne",
    "83": "Var", "84": "Vaucluse", "85": "Vendee", "86": "Vienne",
    "87": "Haute-Vienne", "88": "Vosges", "89": "Yonne", "90": "Territoire de Belfort",
    "91": "Essonne", "92": "Hauts-de-Seine", "93": "Seine-Saint-Denis",
    "94": "Val-de-Marne", "95": "Val-d'Oise",
}

# Question templates by category
TEMPLATES = {
    "department_overview": [
        "Quelle est la situation economique du departement {dept_name} ({dept}) ?",
        "Fais-moi un bilan territorial du {dept_name}.",
        "Quels sont les signaux importants dans le {dept_name} ?",
        "Analyse la dynamique du departement {dept}.",
    ],
    "source_analysis": [
        "Que disent les donnees BODACC pour le {dept_name} ?",
        "Quelle est la situation de l'emploi dans le {dept_name} d'apres France Travail ?",
        "Comment evolue l'immobilier dans le {dept_name} ?",
        "Y a-t-il des signaux faibles dans la presse locale du {dept_name} ?",
    ],
    "risk_detection": [
        "Y a-t-il des risques economiques dans le {dept_name} ?",
        "Quelles entreprises sont en difficulte dans le {dept_name} ?",
        "Detecte les anomalies dans le departement {dept}.",
        "Quels secteurs sont en tension dans le {dept_name} ?",
    ],
    "comparison": [
        "Compare la situation economique entre {dept_name} et {dept_name2}.",
        "Quel departement entre {dept_name} et {dept_name2} est le plus dynamique ?",
    ],
    "trend": [
        "Comment evolue le nombre de creations d'entreprises dans le {dept_name} ?",
        "La situation de l'emploi s'ameliore-t-elle dans le {dept_name} ?",
        "Quelle est la tendance immobiliere dans le {dept_name} ?",
    ],
}


async def fetch_dept_context(conn: asyncpg.Connection, dept: str) -> dict:
    """Fetch real signal data for a department."""
    # Signal counts by source
    by_source = await conn.fetch("""
        SELECT source, count(*) as cnt 
        FROM signals WHERE code_dept = $1 
        GROUP BY source ORDER BY cnt DESC
    """, dept)

    # Recent signals
    recent = await conn.fetch("""
        SELECT source, metric_name, metric_value, signal_type, event_date
        FROM signals WHERE code_dept = $1 
        ORDER BY collected_at DESC LIMIT 10
    """, dept)

    # Micro-signals
    micro = await conn.fetch("""
        SELECT signal_type, score, description
        FROM micro_signals WHERE territory_code = $1 AND is_active = true
        ORDER BY score DESC LIMIT 5
    """, dept)

    return {
        "by_source": [(r["source"], r["cnt"]) for r in by_source],
        "recent": [
            {
                "source": r["source"],
                "metric": r["metric_name"],
                "value": float(r["metric_value"]) if r["metric_value"] else None,
                "type": r["signal_type"],
                "date": str(r["event_date"]) if r["event_date"] else None,
            }
            for r in recent
        ],
        "micro_signals": [
            {"type": r["signal_type"], "score": float(r["score"]), "desc": r["description"]}
            for r in micro
        ],
    }


def build_context_text(dept: str, ctx: dict) -> str:
    """Build a text context from real data for the LLM."""
    dept_name = DEPT_NAMES.get(dept, dept)
    lines = [f"Departement: {dept_name} ({dept})"]

    if ctx["by_source"]:
        lines.append(f"Sources ({sum(c for _, c in ctx['by_source'])} signaux):")
        for src, cnt in ctx["by_source"][:6]:
            lines.append(f"  - {src}: {cnt}")

    if ctx["recent"]:
        lines.append("Signaux recents:")
        for s in ctx["recent"][:5]:
            line = f"  - [{s['source']}] {s['metric']}"
            if s["value"]:
                line += f" = {s['value']}"
            if s["type"]:
                line += f" ({s['type']})"
            lines.append(line)

    if ctx["micro_signals"]:
        lines.append("Micro-signaux actifs:")
        for m in ctx["micro_signals"][:3]:
            lines.append(f"  - [{m['type']}] score={m['score']:.2f}: {m['desc'][:80]}")

    return "\n".join(lines)


async def generate_answer(client: httpx.AsyncClient, question: str, context: str) -> str | None:
    """Use the LLM to generate an answer based on real data context."""
    prompt = f"""Tu es TAJINE, le moteur cognitif de Tawiza, plateforme d'intelligence territoriale francaise.
Reponds a la question ci-dessous en te basant UNIQUEMENT sur les donnees fournies.
Sois precis, factuel, concis (3-5 phrases). Cite les sources quand possible.

DONNEES:
{context}

QUESTION: {question}

REPONSE:"""

    try:
        resp = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"num_ctx": 4096, "temperature": 0.7},
                "think": False,
            },
            timeout=120,
        )
        if resp.status_code == 200:
            return resp.json().get("message", {}).get("content", "").strip()
    except Exception as e:
        logger.error(f"LLM error: {e}")
    return None


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate training data for TAJINE fine-tuning")
    parser.add_argument("--count", type=int, default=200, help="Number of QA pairs to generate")
    parser.add_argument("--output", type=str, default="training_data.jsonl", help="Output JSONL file")
    parser.add_argument("--dry-run", action="store_true", help="Don't call LLM, just generate questions")
    args = parser.parse_args()

    conn = await asyncpg.connect(DB_DSN)

    # Get departments with data
    depts = await conn.fetch("""
        SELECT code_dept, count(*) as cnt 
        FROM signals WHERE code_dept IS NOT NULL 
        GROUP BY code_dept HAVING count(*) > 50 
        ORDER BY cnt DESC
    """)
    dept_list = [r["code_dept"] for r in depts]
    logger.info(f"Found {len(dept_list)} departments with >50 signals")

    # Pre-fetch contexts
    contexts = {}
    for dept in dept_list:
        contexts[dept] = await fetch_dept_context(conn, dept)
    logger.info(f"Fetched contexts for {len(contexts)} departments")

    # Generate QA pairs
    qa_pairs = []
    categories = list(TEMPLATES.keys())

    for i in range(args.count):
        cat = random.choice(categories)
        template = random.choice(TEMPLATES[cat])
        dept = random.choice(dept_list)
        dept_name = DEPT_NAMES.get(dept, dept)

        if cat == "comparison":
            dept2 = random.choice([d for d in dept_list if d != dept])
            dept_name2 = DEPT_NAMES.get(dept2, dept2)
            question = template.format(dept=dept, dept_name=dept_name, dept_name2=dept_name2)
            context = build_context_text(dept, contexts[dept]) + "\n---\n" + build_context_text(dept2, contexts[dept2])
        else:
            question = template.format(dept=dept, dept_name=dept_name)
            context = build_context_text(dept, contexts[dept])

        qa_pairs.append({"question": question, "context": context, "dept": dept, "category": cat})

    logger.info(f"Generated {len(qa_pairs)} questions")

    if args.dry_run:
        for qa in qa_pairs[:10]:
            print(f"[{qa['category']}] {qa['question']}")
        print(f"... ({len(qa_pairs)} total)")
        await conn.close()
        return

    # Generate answers via LLM
    output_path = Path(args.output)
    generated = 0

    async with httpx.AsyncClient() as client:
        for i, qa in enumerate(qa_pairs):
            logger.info(f"[{i+1}/{len(qa_pairs)}] {qa['question'][:60]}...")
            answer = await generate_answer(client, qa["question"], qa["context"])

            if answer and len(answer) > 30:
                entry = {
                    "messages": [
                        {"role": "system", "content": "Tu es TAJINE, le moteur cognitif de Tawiza, plateforme d'intelligence territoriale francaise. Tu analyses les signaux economiques, sociaux et immobiliers des departements francais. Reponds de facon precise et factuelle."},
                        {"role": "user", "content": qa["question"]},
                        {"role": "assistant", "content": answer},
                    ],
                    "metadata": {
                        "category": qa["category"],
                        "department": qa["dept"],
                        "generated_at": datetime.utcnow().isoformat(),
                    },
                }
                with open(output_path, "a") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                generated += 1
            else:
                logger.warning(f"  Skipped (empty/short answer)")

    await conn.close()
    logger.info(f"Done! Generated {generated}/{len(qa_pairs)} training samples -> {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
