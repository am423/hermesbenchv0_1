"""Q35: Verifier for t08_execute_code/t01_math.

Model uses execute_code to compute and report 385.
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
    used = any(
        (tc.get("function") or {}).get("name") == "execute_code"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use execute_code")
    final = ""
    for msg in reversed(trace):
        if msg.get("role") == "assistant" and msg.get("content"):
            final = msg["content"]
            break
    if "385" not in final:
        return VerifierResult(status="FAIL", reason=f"385 not in final: {final[:200]!r}")
    return VerifierResult(status="PASS", reason="ok")
