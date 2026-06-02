"""Q35: Verifier for t07_todo_plan/t01_plan.

Model uses todo with a 4-item list.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class VerifierResult:
    status: Literal["PASS", "FAIL", "SKIPPED", "BUDGET_EXCEEDED", "VERIFIER_ERROR"]
    score: float = 1.0
    reason: str = ""
    details: dict = field(default_factory=dict)


def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = False
    for msg in trace:
        if msg.get("role") == "assistant":
            for tc in (msg.get("tool_calls") or []):
                fn = (tc.get("function") or {})
                if fn.get("name") == "todo":
                    args = fn.get("arguments", "")
                    if isinstance(args, str):
                        try:
                            import json
                            args = json.loads(args)
                        except Exception:
                            continue
                    if isinstance(args, dict):
                        todos = args.get("todos", [])
                        if isinstance(todos, list) and len(todos) >= 4:
                            used = True
    if not used:
        return VerifierResult(status="FAIL", reason="model did not create a 4-item todo list")
    return VerifierResult(status="PASS", reason="ok")
