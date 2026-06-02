"""Q35: Verifier for t08_execute_code/t05_stateful.

Model uses execute_code twice.
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
        if (tc.get("function") or {}).get("name") == "execute_code"
    )
    if n < 2:
        return VerifierResult(status="FAIL", reason=f"expected >=2 execute_code calls, got {n}")
    return VerifierResult(status="PASS", reason="ok")
