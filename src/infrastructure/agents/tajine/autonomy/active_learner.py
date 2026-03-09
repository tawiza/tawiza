"""Active Learner - Autonomous data collection driven by knowledge gaps.

When the TAJINE agent detects gaps in the Knowledge Graph, the Active Learner
decides what data to collect next and triggers targeted collection.

This closes the loop: 
    Agent analyzes → finds gaps → triggers collection → new signals → KG rebuilds → repeat

Architecture:
    TerritorialKG.find_gaps() → ActiveLearner.prioritize() → Collector V2 → signals DB
"""

import asyncio
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import asyncpg
from loguru import logger


def _find_project_root() -> Path:
    """Walk up from this file to find the project root (contains pyproject.toml)."""
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    return Path.cwd()


_PROJECT_ROOT = _find_project_root()

DB_URL = os.getenv(
    "COLLECTOR_DATABASE_URL",
    "postgresql://localhost:5433/tawiza"
).replace("postgresql+asyncpg://", "postgresql://").replace("postgresql://", "postgres://")


class ActiveLearner:
    """Autonomous data collection planner.
    
    Analyzes knowledge gaps and prioritizes what to collect next.
    Can trigger collection jobs automatically or return recommendations.
    """

    def __init__(self, auto_collect: bool = False):
        """Initialize.
        
        Args:
            auto_collect: If True, automatically trigger collection.
                         If False, only return recommendations.
        """
        self.auto_collect = auto_collect
        self._last_run: datetime | None = None
        self._collection_history: list[dict] = []

    async def analyze_and_plan(self, gaps: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze gaps and create a collection plan.
        
        Args:
            gaps: Gaps from TerritorialKG.find_gaps()
            
        Returns:
            Collection plan with prioritized actions
        """
        if not gaps:
            return {"status": "no_gaps", "actions": []}
        
        plan = {
            "timestamp": datetime.now().isoformat(),
            "total_gaps": len(gaps),
            "actions": [],
        }
        
        # Group by type
        by_type: dict[str, list] = {}
        for gap in gaps:
            t = gap.get("type", "unknown")
            by_type.setdefault(t, []).append(gap)
        
        # Priority 1: Missing sources for departments
        for gap in by_type.get("missing_sources", []):
            dept = gap["department"]
            missing = gap.get("missing_sources", [])
            for source in missing[:3]:  # Max 3 per department
                plan["actions"].append({
                    "type": "collect",
                    "source": source,
                    "department": dept,
                    "priority": gap["priority"],
                    "reason": f"Dept {dept} missing {source} data",
                })
        
        # Priority 2: Low coverage departments
        for gap in by_type.get("low_coverage", []):
            dept = gap["department"]
            plan["actions"].append({
                "type": "full_collect",
                "department": dept,
                "priority": 1,
                "reason": f"Dept {dept} has only {gap['total_signals']} signals",
            })
        
        # Priority 3: Sources not covering enough departments
        for gap in by_type.get("source_low_coverage", []):
            plan["actions"].append({
                "type": "expand_source",
                "source": gap["source"],
                "priority": 2,
                "reason": f"{gap['source']} only covers {gap['departments_covered']} departments",
            })
        
        # Priority 4: Re-run detection
        for gap in by_type.get("no_anomalies_detected", []):
            plan["actions"].append({
                "type": "rerun_detection",
                "department": gap["department"],
                "priority": 3,
                "reason": gap["suggestion"],
            })
        
        # Sort by priority
        plan["actions"].sort(key=lambda a: a["priority"])
        
        # Auto-collect if enabled
        if self.auto_collect and plan["actions"]:
            executed = await self._execute_plan(plan["actions"][:5])  # Max 5 at a time
            plan["executed"] = executed
        
        self._last_run = datetime.now()
        return plan

    async def _execute_plan(self, actions: list[dict]) -> list[dict]:
        """Execute collection actions.
        
        Uses the collector scripts to gather data.
        """
        results = []
        for action in actions:
            try:
                if action["type"] in ("collect", "full_collect"):
                    result = await self._run_collection(
                        department=action.get("department"),
                        source=action.get("source"),
                    )
                    results.append({**action, "result": result})
                elif action["type"] == "rerun_detection":
                    result = await self._run_detection(action.get("department"))
                    results.append({**action, "result": result})
                else:
                    results.append({**action, "result": "skipped"})
            except Exception as e:
                results.append({**action, "result": f"error: {e}"})
        
        self._collection_history.extend(results)
        return results

    async def _run_collection(
        self, department: str | None = None, source: str | None = None
    ) -> str:
        """Run a targeted collection."""
        # Build command
        script = str(_PROJECT_ROOT / "src" / "scripts" / "collect_all_v2.py")
        cmd = ["python3", script]
        if department:
            cmd.extend(["--dept", department])
        if source:
            cmd.extend(["--source", source])

        logger.info(f"Active Learner: collecting {source or 'all'} for dept {department or 'all'}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(_PROJECT_ROOT),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
            if proc.returncode == 0:
                return f"success: {stdout.decode()[-200:]}"
            else:
                return f"failed (code {proc.returncode}): {stderr.decode()[-200:]}"
        except asyncio.TimeoutError:
            return "timeout (300s)"
        except Exception as e:
            return f"error: {e}"

    async def _run_detection(self, department: str | None = None) -> str:
        """Run micro-signal detection."""
        script = str(_PROJECT_ROOT / "src" / "scripts" / "detect_microsignals_v2.py")
        cmd = ["python3", script]
        if department:
            cmd.extend(["--dept", department])

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(_PROJECT_ROOT),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
            return f"detection {'ok' if proc.returncode == 0 else 'failed'}"
        except Exception as e:
            return f"error: {e}"

    def get_status(self) -> dict[str, Any]:
        """Get active learner status."""
        return {
            "auto_collect": self.auto_collect,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "total_actions_executed": len(self._collection_history),
            "recent_actions": self._collection_history[-5:] if self._collection_history else [],
        }
