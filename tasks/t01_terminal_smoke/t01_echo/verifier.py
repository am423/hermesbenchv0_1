"""Q35: Verifier for t01_terminal_smoke/t01_echo.

Model uses terminal tool to run an echo and reports the output.
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
    used_terminal = False
    for msg in trace:
        if msg.get("role") == "assistant":
            for tc in (msg.get("tool_calls") or []):
                if (tc.get("function") or {}).get("name") == "terminal":
                    used_terminal = True
    if not used_terminal:
        return VerifierResult(status="FAIL", reason="model did not use terminal tool")
    final = ""
    for msg in reversed(trace):
        if msg.get("role") == "assistant" and msg.get("content"):
            final = msg["content"]
            break
    if "hello-hermesbench" not in final:
        return VerifierResult(
            status="FAIL", reason=f"final message missing 'hello-hermesbench': {final[:200]!r}"
        )
    return VerifierResult(status="PASS", reason="ok")
