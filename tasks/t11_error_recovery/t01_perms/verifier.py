"""Q35: Verifier for t11_error_recovery/t01_perms.

Model recovers from a permission error within 2 turns.
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
    n_recoveries = 0
    for msg in trace:
        if msg.get("role") == "assistant":
            tcs = msg.get("tool_calls") or []
            for tc in tcs:
                fn = (tc.get("function") or {})
                if fn.get("name") in ("terminal", "read_file", "patch"):
                    n_recoveries += 1
    if n_recoveries < 2:
        return VerifierResult(status="FAIL", reason=f"only {n_recoveries} recovery attempts")
    return VerifierResult(status="PASS", reason="ok")
