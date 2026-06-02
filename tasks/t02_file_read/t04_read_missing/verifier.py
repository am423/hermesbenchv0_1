"""Q35: Verifier for t02_file_read/t04_read_missing.

Model attempts to read missing file and recovers.
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
    attempted = False
    for msg in trace:
        if msg.get("role") == "assistant":
            for tc in (msg.get("tool_calls") or []):
                fn = (tc.get("function") or {})
                if fn.get("name") == "read_file":
                    args = fn.get("arguments", "")
                    if isinstance(args, str) and "nonexistent" in args:
                        attempted = True
    if not attempted:
        return VerifierResult(status="FAIL", reason="model did not attempt the missing file")
    return VerifierResult(status="PASS", reason="ok")
