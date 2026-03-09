"""TAJINE ReAct Agent — Reason + Act loop for autonomous territorial analysis.

The agent receives a question, then iterates:
  1. THINK: reason about what information is needed
  2. ACT: call a tool (DB query, KG lookup, watcher alerts, relations, etc.)
  3. OBSERVE: process tool output
  4. ... repeat until ready to answer
  5. ANSWER: produce final structured response

Tools available:
  - query_signals: Search signals by dept/source/metric/text
  - department_profile: Get composite scores + stats for a department
  - microsignals: Get active micro-signals for a territory
  - convergences: Get cross-dimension convergences
  - anomalies: Get ML anomaly detection results
  - watcher_alerts: Get recent monitoring alerts
  - relations: Get actor network for a department
  - predictions: Get Prophet forecasts
  - compare_departments: Compare 2+ departments side by side
  - knowledge_graph: Query the territorial knowledge graph
"""

import asyncio
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

import asyncpg
import httpx
from loguru import logger

DB_URL = "postgresql://tawiza:tawiza2026@localhost:5433/tawiza"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL = "qwen3.5:27b"
MAX_ITERATIONS = 6
MAX_TOOL_OUTPUT = 1500  # chars per tool output


@dataclass
class ToolCall:
    name: str
    args: dict
    result: str = ""


@dataclass
class AgentStep:
    thought: str
    action: str | None = None
    action_input: dict | None = None
    observation: str | None = None


@dataclass
class AgentResult:
    answer: str
    steps: list[AgentStep] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    confidence: float = 0.7
    department: str | None = None
    citations: list[str] = field(default_factory=list)


# ─── Tools ────────────────────────────────────────────────────

async def _get_conn():
    return await asyncpg.connect(DB_URL)


async def tool_query_signals(args: dict) -> str:
    """Search signals with filters."""
    conn = await _get_conn()
    try:
        conditions = ["1=1"]
        params = []
        idx = 1

        if args.get("dept"):
            conditions.append(f"code_dept = ${idx}")
            params.append(args["dept"])
            idx += 1
        if args.get("source"):
            conditions.append(f"source = ${idx}")
            params.append(args["source"])
            idx += 1
        if args.get("metric"):
            conditions.append(f"metric_name ILIKE ${idx}")
            params.append(f"%{args['metric']}%")
            idx += 1
        if args.get("text"):
            conditions.append(f"extracted_text ILIKE ${idx}")
            params.append(f"%{args['text']}%")
            idx += 1

        where = " AND ".join(conditions)
        limit = min(args.get("limit", 10), 20)

        rows = await conn.fetch(f"""
            SELECT id, source, metric_name, code_dept, metric_value, event_date, extracted_text
            FROM signals WHERE {where}
            ORDER BY collected_at DESC LIMIT ${idx}
        """, *params, limit)

        results = []
        for r in rows:
            text = (r['extracted_text'] or '')[:200]
            results.append(
                f"[SIG-{r['id']}] {r['source']}/{r['metric_name']} dept={r['code_dept']} "
                f"val={r['metric_value']} date={r['event_date']} | {text}"
            )
        return f"{len(rows)} signaux trouves:\n" + "\n".join(results) if results else "Aucun signal trouve."
    finally:
        await conn.close()


async def tool_department_profile(args: dict) -> str:
    """Get department stats and signal counts."""
    dept = args.get("dept", "75")
    conn = await _get_conn()
    try:
        # Signal counts by source
        counts = await conn.fetch("""
            SELECT source, count(*) as cnt FROM signals
            WHERE code_dept = $1 GROUP BY source ORDER BY cnt DESC
        """, dept)

        # Key metrics (latest values)
        metrics = await conn.fetch("""
            SELECT DISTINCT ON (metric_name) metric_name, metric_value, event_date, source
            FROM signals WHERE code_dept = $1 AND metric_value IS NOT NULL
            ORDER BY metric_name, collected_at DESC
            LIMIT 20
        """, dept)

        # Micro-signals count
        ms_count = await conn.fetchval("""
            SELECT count(*) FROM micro_signals WHERE is_active = TRUE AND territory_code = $1
        """, dept)

        total = sum(r['cnt'] for r in counts)
        lines = [
            f"Dept {dept} — {total} signaux totaux, {ms_count} micro-signaux actifs",
            f"  Sources: " + ", ".join(f"{r['source']}={r['cnt']}" for r in counts),
        ]

        if metrics:
            lines.append("  Metriques recentes:")
            for m in metrics[:10]:
                lines.append(f"    {m['source']}/{m['metric_name']}: {m['metric_value']:.2f} ({m['event_date']})")

        return "\n".join(lines)
    finally:
        await conn.close()


async def tool_microsignals(args: dict) -> str:
    """Get active micro-signals."""
    dept = args.get("dept")
    conn = await _get_conn()
    try:
        if dept:
            rows = await conn.fetch("""
                SELECT territory_code, signal_type, score, description
                FROM micro_signals WHERE is_active = TRUE AND territory_code = $1
                ORDER BY score DESC LIMIT 10
            """, dept)
        else:
            rows = await conn.fetch("""
                SELECT territory_code, signal_type, score, description
                FROM micro_signals WHERE is_active = TRUE
                ORDER BY score DESC LIMIT 15
            """)

        if not rows:
            return "Aucun micro-signal actif" + (f" pour {dept}" if dept else "")

        lines = [f"{r['territory_code']}: {r['signal_type']} (score={r['score']:.2f}) — {(r['description'] or '')[:100]}" for r in rows]
        return f"{len(rows)} micro-signaux:\n" + "\n".join(lines)
    finally:
        await conn.close()


async def tool_convergences(args: dict) -> str:
    """Get cross-dimension convergences."""
    conn = await _get_conn()
    try:
        rows = await conn.fetch("""
            SELECT territory_code, signal_type, score, dimensions, description
            FROM micro_signals
            WHERE is_active = TRUE AND signal_type ILIKE '%convergence%'
            ORDER BY score DESC LIMIT 10
        """)
        if not rows:
            return "Aucune convergence detectee."

        lines = []
        for r in rows:
            dims = r['dimensions'] if isinstance(r['dimensions'], list) else []
            lines.append(f"{r['territory_code']}: score={r['score']:.2f}, dimensions={','.join(dims)}")
        return f"{len(rows)} convergences:\n" + "\n".join(lines)
    finally:
        await conn.close()


async def tool_anomalies(args: dict) -> str:
    """Get ML anomaly detection results."""
    conn = await _get_conn()
    try:
        rows = await conn.fetch("""
            SELECT department, risk_score, isolation_forest, convergence_score, nb_micro_signals
            FROM anomaly_detection_v2
            WHERE department != 'FR'
            ORDER BY risk_score DESC LIMIT 10
        """)
        if not rows:
            return "Aucune anomalie detectee."

        lines = []
        for r in rows:
            iso = json.loads(r['isolation_forest']) if r['isolation_forest'] else {}
            contribs = iso.get('contributing', [])
            top_feat = contribs[0]['feature'] if contribs else 'N/A'
            lines.append(
                f"{r['department']}: risque={r['risk_score']:.2f}, "
                f"convergence={r['convergence_score']:.2f}, microsignaux={r['nb_micro_signals']}, "
                f"facteur_principal={top_feat}"
            )
        return f"{len(rows)} anomalies ML (top risque):\n" + "\n".join(lines)
    finally:
        await conn.close()


async def tool_watcher_alerts(args: dict) -> str:
    """Get recent watcher monitoring alerts."""
    dept = args.get("dept")
    conn = await _get_conn()
    try:
        if dept:
            rows = await conn.fetch("""
                SELECT department, metric, priority, z_score, direction, message
                FROM watcher_alerts WHERE acknowledged = FALSE AND department = $1
                ORDER BY detected_at DESC LIMIT 10
            """, dept)
        else:
            rows = await conn.fetch("""
                SELECT department, metric, priority, z_score, direction, message
                FROM watcher_alerts WHERE acknowledged = FALSE
                ORDER BY detected_at DESC LIMIT 15
            """)

        if not rows:
            return "Aucune alerte active" + (f" pour {dept}" if dept else "")

        lines = [f"[{r['priority']}] {r['message']}" for r in rows]
        return f"{len(rows)} alertes:\n" + "\n".join(lines)
    finally:
        await conn.close()


async def tool_predictions(args: dict) -> str:
    """Get Prophet forecast predictions."""
    dept = args.get("dept")
    conn = await _get_conn()
    try:
        if dept:
            rows = await conn.fetch("""
                SELECT department, metric, label, trend, change_pct, data_points
                FROM predictions_prophet WHERE department = $1
                ORDER BY abs(change_pct) DESC LIMIT 10
            """, dept)
        else:
            rows = await conn.fetch("""
                SELECT department, metric, label, trend, change_pct, data_points
                FROM predictions_prophet
                ORDER BY abs(change_pct) DESC LIMIT 10
            """)

        if not rows:
            return "Aucune prediction disponible" + (f" pour {dept}" if dept else "")

        lines = [f"{r['department']}: {r['label']} → {r['trend']} ({r['change_pct']:+.1f}%, {r['data_points']} points)" for r in rows]
        return f"{len(rows)} predictions:\n" + "\n".join(lines)
    finally:
        await conn.close()


async def tool_compare_departments(args: dict) -> str:
    """Compare 2+ departments side by side."""
    depts = args.get("depts", [])
    if len(depts) < 2:
        return "Il faut au moins 2 departements a comparer."

    conn = await _get_conn()
    try:
        rows = await conn.fetch("""
            SELECT code_dept, score_composite,
                alpha1_sante_entreprises, alpha2_tension_emploi,
                alpha3_dynamisme_immo, alpha4_sante_financiere,
                alpha5_declin_ratio, alpha6_sentiment
            FROM scoring_composite WHERE code_dept = ANY($1)
        """, depts)

        if not rows:
            return "Aucune donnee pour ces departements."

        header = f"{'Dim':<15}" + "".join(f"{r['code_dept']:>8}" for r in rows)
        lines = [header, "-" * len(header)]

        for label, key in [
            ("Score", "score_composite"), ("Entreprises", "alpha1_sante_entreprises"),
            ("Emploi", "alpha2_tension_emploi"), ("Immobilier", "alpha3_dynamisme_immo"),
            ("Finances", "alpha4_sante_financiere"), ("Declin", "alpha5_declin_ratio"),
            ("Sentiment", "alpha6_sentiment"),
        ]:
            line = f"{label:<15}" + "".join(f"{r[key]:>8.1f}" for r in rows)
            lines.append(line)

        return "\n".join(lines)
    finally:
        await conn.close()


async def tool_knowledge_graph(args: dict) -> str:
    """Query the territorial knowledge graph."""
    dept = args.get("dept")
    conn = await _get_conn()
    try:
        # Get causal links from KG-like data
        rows = await conn.fetch("""
            SELECT DISTINCT s1.source as src1, s2.source as src2, s1.code_dept,
                   s1.metric_name as m1, s2.metric_name as m2
            FROM signals s1
            JOIN signals s2 ON s1.code_dept = s2.code_dept AND s1.source != s2.source
            WHERE s1.code_dept = $1
            AND s1.event_date > NOW() - INTERVAL '90 days'
            AND s2.event_date > NOW() - INTERVAL '90 days'
            LIMIT 20
        """, dept or "75")

        if not rows:
            return f"Aucun lien inter-sources pour {dept or '75'}"

        sources = set()
        for r in rows:
            sources.add(f"{r['src1']}({r['m1'][:20]}) → {r['src2']}({r['m2'][:20]})")

        return f"Liens inter-sources pour dept {dept or '75'}:\n" + "\n".join(list(sources)[:15])
    finally:
        await conn.close()


# ─── Tool Registry ────────────────────────────────────────────

TOOLS = {
    "query_signals": {
        "fn": tool_query_signals,
        "desc": "Chercher des signaux dans la base. Args: dept, source, metric, text, limit",
    },
    "department_profile": {
        "fn": tool_department_profile,
        "desc": "Profil complet d'un departement (scores, stats). Args: dept",
    },
    "microsignals": {
        "fn": tool_microsignals,
        "desc": "Micro-signaux actifs (anomalies detectees). Args: dept (optionnel)",
    },
    "convergences": {
        "fn": tool_convergences,
        "desc": "Convergences multi-dimensionnelles (croisement de sources). Pas d'args requis",
    },
    "anomalies": {
        "fn": tool_anomalies,
        "desc": "Anomalies ML (Isolation Forest + DBSCAN). Pas d'args requis",
    },
    "watcher_alerts": {
        "fn": tool_watcher_alerts,
        "desc": "Alertes de surveillance en temps reel. Args: dept (optionnel)",
    },
    "predictions": {
        "fn": tool_predictions,
        "desc": "Predictions Prophet (tendances a 3 mois). Args: dept (optionnel)",
    },
    "compare_departments": {
        "fn": tool_compare_departments,
        "desc": "Comparer 2+ departements. Args: depts (liste de codes)",
    },
    "knowledge_graph": {
        "fn": tool_knowledge_graph,
        "desc": "Liens causaux inter-sources pour un departement. Args: dept",
    },
}

TOOLS_DESC = "\n".join(f"- {name}: {t['desc']}" for name, t in TOOLS.items())


# ─── ReAct Loop ───────────────────────────────────────────────

REACT_SYSTEM = f"""Tu es TAJINE, un agent d'intelligence territoriale autonome.
Tu analyses l'economie des 101 departements francais en utilisant des outils.

OUTILS DISPONIBLES:
{TOOLS_DESC}

PROCESSUS: Pour chaque question, tu dois:
1. PENSER a ce dont tu as besoin
2. UTILISER un outil si necessaire
3. OBSERVER le resultat
4. REPETER si besoin (max {MAX_ITERATIONS} iterations)
5. REPONDRE avec une synthese structuree

FORMAT STRICT:
THOUGHT: [ton raisonnement]
ACTION: [nom_outil]
ACTION_INPUT: {{"arg1": "val1", "arg2": "val2"}}

Quand tu as assez d'information:
THOUGHT: J'ai assez d'information pour repondre.
ANSWER: [ta reponse finale structuree, avec citations [SIG-xxx] si disponibles]

REGLES:
- Toujours commencer par THOUGHT
- Un seul ACTION par iteration
- ACTION_INPUT doit etre du JSON valide
- ANSWER termine la boucle
- Cite les signaux [SIG-xxx] quand pertinent
- Reponds en francais, avec chiffres concrets
- Sois concis mais complet
"""


async def _call_llm(messages: list[dict], temperature: float = 0.3) -> str:
    """Call Ollama with messages."""
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{OLLAMA_HOST}/api/chat",
            json={
                "model": MODEL,
                "messages": messages,
                "stream": False,
                "think": False,
                "options": {"temperature": temperature, "num_predict": 1024, "num_ctx": 4096},
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")


def _parse_react_output(text: str) -> dict:
    """Parse THOUGHT/ACTION/ACTION_INPUT/ANSWER from LLM output."""
    result = {"thought": "", "action": None, "action_input": None, "answer": None}

    # Extract THOUGHT
    thought_match = re.search(r'THOUGHT:\s*(.+?)(?=ACTION:|ANSWER:|$)', text, re.DOTALL)
    if thought_match:
        result["thought"] = thought_match.group(1).strip()

    # Extract ANSWER (takes priority)
    answer_match = re.search(r'ANSWER:\s*(.+)', text, re.DOTALL)
    if answer_match:
        result["answer"] = answer_match.group(1).strip()
        return result

    # Extract ACTION
    action_match = re.search(r'ACTION:\s*(\w+)', text)
    if action_match:
        result["action"] = action_match.group(1).strip()

    # Extract ACTION_INPUT
    input_match = re.search(r'ACTION_INPUT:\s*(\{.*?\})', text, re.DOTALL)
    if input_match:
        try:
            result["action_input"] = json.loads(input_match.group(1))
        except json.JSONDecodeError:
            result["action_input"] = {}

    return result


async def run_react_agent(
    query: str,
    department: str | None = None,
    max_iterations: int = MAX_ITERATIONS,
) -> AgentResult:
    """Run the ReAct agent loop."""
    logger.info(f"[REACT] Starting agent for: {query[:80]}...")

    messages = [
        {"role": "system", "content": REACT_SYSTEM},
    ]

    # Add department context hint
    if department:
        messages.append({"role": "user", "content": f"Contexte: departement cible = {department}\n\nQuestion: {query}"})
    else:
        messages.append({"role": "user", "content": f"Question: {query}"})

    steps = []
    tools_used = []
    citations = []

    for i in range(max_iterations):
        logger.info(f"[REACT] Iteration {i+1}/{max_iterations}")

        # Call LLM
        llm_output = await _call_llm(messages)
        logger.debug(f"[REACT] LLM output: {llm_output[:200]}...")

        # Parse
        parsed = _parse_react_output(llm_output)

        step = AgentStep(
            thought=parsed["thought"],
            action=parsed["action"],
            action_input=parsed["action_input"],
        )

        # If ANSWER, we're done
        if parsed["answer"]:
            logger.info(f"[REACT] Agent answered after {i+1} iterations")
            # Extract citations
            cites = re.findall(r'\[SIG-(\d+)\]', parsed["answer"])
            return AgentResult(
                answer=parsed["answer"],
                steps=steps,
                tools_used=list(set(tools_used)),
                confidence=min(0.5 + 0.1 * len(tools_used), 0.95),
                department=department,
                citations=cites,
            )

        # Execute tool
        if parsed["action"] and parsed["action"] in TOOLS:
            tool_name = parsed["action"]
            tool_args = parsed["action_input"] or {}

            logger.info(f"[REACT] Calling tool: {tool_name}({tool_args})")
            tools_used.append(tool_name)

            try:
                tool_fn = TOOLS[tool_name]["fn"]
                tool_result = await tool_fn(tool_args)
                # Truncate
                if len(tool_result) > MAX_TOOL_OUTPUT:
                    tool_result = tool_result[:MAX_TOOL_OUTPUT] + "\n... (tronque)"
            except Exception as e:
                tool_result = f"ERREUR: {e}"
                logger.warning(f"[REACT] Tool error: {e}")

            step.observation = tool_result

            # Add to conversation
            messages.append({"role": "assistant", "content": llm_output})
            messages.append({"role": "user", "content": f"OBSERVATION:\n{tool_result}"})
        else:
            # No valid action and no answer — force conclusion
            if parsed["action"] and parsed["action"] not in TOOLS:
                messages.append({"role": "assistant", "content": llm_output})
                messages.append({"role": "user", "content": f"OBSERVATION: Outil '{parsed['action']}' non disponible. Outils: {', '.join(TOOLS.keys())}. Reponds avec ANSWER si tu as assez d'info."})
            else:
                # Force answer
                messages.append({"role": "assistant", "content": llm_output})
                messages.append({"role": "user", "content": "Tu n'as pas specifie d'ACTION ni d'ANSWER. Reponds avec ANSWER: suivi de ta reponse."})

        steps.append(step)

    # Max iterations reached — force answer from what we have
    logger.warning(f"[REACT] Max iterations ({max_iterations}) reached, forcing answer")
    messages.append({"role": "user", "content": "Tu as atteint le maximum d'iterations. Reponds maintenant avec ANSWER: suivi de ta synthese basee sur les informations collectees."})
    final_output = await _call_llm(messages)
    parsed = _parse_react_output(final_output)

    return AgentResult(
        answer=parsed.get("answer") or parsed.get("thought") or final_output,
        steps=steps,
        tools_used=list(set(tools_used)),
        confidence=min(0.4 + 0.1 * len(tools_used), 0.9),
        department=department,
        citations=re.findall(r'\[SIG-(\d+)\]', final_output),
    )


# ─── Streaming variant ───────────────────────────────────────

async def stream_react_agent(
    query: str,
    department: str | None = None,
    max_iterations: int = MAX_ITERATIONS,
):
    """Generator that yields SSE events for each step of the ReAct loop."""
    import json as json_mod

    logger.info(f"[REACT-STREAM] Starting for: {query[:80]}...")

    messages = [
        {"role": "system", "content": REACT_SYSTEM},
    ]

    if department:
        messages.append({"role": "user", "content": f"Contexte: departement cible = {department}\n\nQuestion: {query}"})
    else:
        messages.append({"role": "user", "content": f"Question: {query}"})

    tools_used = []

    for i in range(max_iterations):
        yield f"data: {json_mod.dumps({'type': 'step', 'iteration': i+1, 'status': 'thinking'})}\n\n"

        llm_output = await _call_llm(messages)
        parsed = _parse_react_output(llm_output)

        if parsed["thought"]:
            yield f"data: {json_mod.dumps({'type': 'thought', 'text': parsed['thought']})}\n\n"

        if parsed["answer"]:
            yield f"data: {json_mod.dumps({'type': 'answer', 'text': parsed['answer'], 'tools_used': list(set(tools_used)), 'iterations': i+1})}\n\n"
            return

        if parsed["action"] and parsed["action"] in TOOLS:
            tool_name = parsed["action"]
            tool_args = parsed["action_input"] or {}
            tools_used.append(tool_name)

            yield f"data: {json_mod.dumps({'type': 'tool_call', 'tool': tool_name, 'args': tool_args})}\n\n"

            try:
                tool_result = await TOOLS[tool_name]["fn"](tool_args)
                if len(tool_result) > MAX_TOOL_OUTPUT:
                    tool_result = tool_result[:MAX_TOOL_OUTPUT] + "\n... (tronque)"
            except Exception as e:
                tool_result = f"ERREUR: {e}"

            yield f"data: {json_mod.dumps({'type': 'observation', 'text': tool_result[:500]})}\n\n"

            messages.append({"role": "assistant", "content": llm_output})
            messages.append({"role": "user", "content": f"OBSERVATION:\n{tool_result}"})
        else:
            messages.append({"role": "assistant", "content": llm_output})
            if parsed["action"]:
                messages.append({"role": "user", "content": f"OBSERVATION: Outil '{parsed['action']}' non disponible. Outils: {', '.join(TOOLS.keys())}."})
            else:
                messages.append({"role": "user", "content": "Reponds avec ANSWER: suivi de ta synthese."})

    # Force final
    messages.append({"role": "user", "content": "Maximum d'iterations atteint. ANSWER:"})
    final = await _call_llm(messages)
    parsed = _parse_react_output(final)
    yield f"data: {json_mod.dumps({'type': 'answer', 'text': parsed.get('answer') or final, 'tools_used': list(set(tools_used)), 'iterations': max_iterations})}\n\n"
