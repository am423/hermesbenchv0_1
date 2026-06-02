"""Q35: Verifier for t01_terminal_smoke/t04_pipeline.

Model runs the pipeline.
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
                if fn.get("name") == "terminal":
                    args = fn.get("arguments", "")
                    if isinstance(args, str) and "cat" in args and "grep" in args and "wc" in args:
                        used = True
    if not used:
        return VerifierResult(status="FAIL", reason="model did not run the pipe")
    return VerifierResult(status="PASS", reason="ok")
