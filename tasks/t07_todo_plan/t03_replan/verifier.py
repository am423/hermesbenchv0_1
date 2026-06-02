"""Q35: Verifier for t07_todo_plan/t03_replan.

Model calls todo at least 2 times (initial plan + replan).
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
    n = sum(
        1 for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
        if (tc.get("function") or {}).get("name") == "todo"
    )
    if n < 2:
        return VerifierResult(status="FAIL", reason=f"expected >=2 todo calls (replan), got {n}")
    return VerifierResult(status="PASS", reason="ok")
