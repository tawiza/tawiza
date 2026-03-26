"""Training data API  -  generate, list, and manage training datasets for fine-tuning.

Provides endpoints for synthetic dataset generation from real signals
and management of training data files.
"""

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from src.infrastructure.security.validators import safe_path

router = APIRouter(prefix="/api/v1/training", tags=["Training Data"])

DB_DSN = os.getenv(
    "COLLECTOR_DATABASE_URL",
    "postgresql://localhost:5432/tawiza",
).replace("+asyncpg", "")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "training_data"

_gen_state: dict[str, Any] = {
    "is_running": False,
    "progress": 0,
    "total": 0,
    "last_run": None,
    "error": None,
}


async def _run_generation(count: int, output_name: str):
    global _gen_state
    _gen_state["is_running"] = True
    _gen_state["progress"] = 0
    _gen_state["total"] = count
    _gen_state["error"] = None

    DATA_DIR.mkdir(exist_ok=True)
    output = DATA_DIR / output_name

    try:
        script = (
            Path(__file__).resolve().parent.parent.parent.parent
            / "scripts"
            / "generate_training_data.py"
        )
        proc = await asyncio.create_subprocess_exec(
            "python3",
            str(script),
            "--count",
            str(count),
            "--output",
            str(output),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(PROJECT_ROOT),
        )
        stdout, stderr = await proc.communicate()
        _gen_state["last_run"] = datetime.now(UTC).isoformat()
        if proc.returncode != 0:
            _gen_state["error"] = stderr.decode()[-300:]
    except Exception as e:
        _gen_state["error"] = str(e)
    finally:
        _gen_state["is_running"] = False


@router.get("/datasets")
async def list_datasets():
    """List available training datasets."""
    DATA_DIR.mkdir(exist_ok=True)
    datasets = []
    for f in sorted(DATA_DIR.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        stat = f.stat()
        # Count lines
        with open(f) as fh:
            line_count = sum(1 for _ in fh)
        datasets.append(
            {
                "name": f.name,
                "size_bytes": stat.st_size,
                "samples": line_count,
                "created_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
            }
        )
    return {"datasets": datasets, "total": len(datasets)}


@router.get("/datasets/{name}")
async def get_dataset_preview(name: str, offset: int = 0, limit: int = 10):
    """Preview a training dataset (paginated)."""
    name = os.path.basename(name)
    try:
        fpath = safe_path(DATA_DIR, name)
    except ValueError:
        raise HTTPException(400, "Invalid dataset name")
    if not fpath.exists() or not fpath.suffix == ".jsonl":
        raise HTTPException(404, f"Dataset {name} not found")

    samples = []
    with open(fpath) as f:
        for i, line in enumerate(f):
            if i < offset:
                continue
            if i >= offset + limit:
                break
            try:
                samples.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    with open(fpath) as f:
        total = sum(1 for _ in f)
    return {"name": name, "total": total, "offset": offset, "samples": samples}


@router.post("/generate")
async def generate_dataset(
    bg: BackgroundTasks,
    count: int = Query(200, ge=10, le=2000),
    name: str = Query(None),
):
    """Generate a synthetic training dataset from real signals (background task)."""
    if _gen_state["is_running"]:
        raise HTTPException(409, "Generation already running")

    output_name = name or f"tajine_training_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    if not output_name.endswith(".jsonl"):
        output_name += ".jsonl"

    bg.add_task(_run_generation, count, output_name)
    return {
        "status": "started",
        "count": count,
        "output": output_name,
    }


@router.get("/generate/status")
async def generation_status():
    """Status of the current/last dataset generation."""
    return _gen_state


@router.get("/stats")
async def training_stats():
    """Training data statistics."""
    conn = await asyncpg.connect(DB_DSN)
    try:
        # Count interactions from conversations table if it exists
        try:
            interactions = await conn.fetchval("SELECT count(*) FROM messages")
        except Exception:
            interactions = 0

        # Count feedbacks
        try:
            positive = await conn.fetchval("SELECT count(*) FROM feedbacks WHERE rating > 0")
            negative = await conn.fetchval("SELECT count(*) FROM feedbacks WHERE rating <= 0")
        except Exception:
            positive = 0
            negative = 0

        # Count datasets
        DATA_DIR.mkdir(exist_ok=True)
        datasets = list(DATA_DIR.glob("*.jsonl"))
        total_samples = 0
        for d in datasets:
            with open(d) as f:
                total_samples += sum(1 for _ in f)

        return {
            "total_interactions": interactions,
            "success_traces": total_samples,
            "preference_pairs": 0,
            "positive_feedback": positive,
            "negative_feedback": negative,
            "avg_quality_score": 0.0,
            "last_collected": _gen_state["last_run"],
            "ready_for_sft": total_samples >= 50,
            "ready_for_dpo": False,
            "datasets_count": len(datasets),
            "total_samples": total_samples,
        }
    finally:
        await conn.close()
