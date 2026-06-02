"""Q35: Verifier for t11_error_recovery/t03_transient.

Model retries after a transient error.
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
    n_curl = 0
    for msg in trace:
        if msg.get("role") == "assistant":
            for tc in (msg.get("tool_calls") or []):
                fn = (tc.get("function") or {})
                if fn.get("name") == "terminal":
                    args = fn.get("arguments", "")
                    if isinstance(args, str) and "curl" in args:
                        n_curl += 1
    if n_curl < 2:
        return VerifierResult(status="FAIL", reason=f"expected >=2 curl calls (retry), got {n_curl}")
    return VerifierResult(status="PASS", reason="ok")
