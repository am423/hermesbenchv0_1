"""Q35: Verifier for t02_file_read/t03_read_paginated.

Model calls read_file at least 3 times with offset/limit.
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
    n = 0
    for msg in trace:
        if msg.get("role") == "assistant":
            for tc in (msg.get("tool_calls") or []):
                fn = (tc.get("function") or {})
                if fn.get("name") == "read_file":
                    args = fn.get("arguments", "")
                    if isinstance(args, str):
                        try:
                            import json
                            args = json.loads(args)
                        except Exception:
                            continue
                    if isinstance(args, dict) and "offset" in args:
                        n += 1
    if n < 3:
        return VerifierResult(status="FAIL", reason=f"expected >=3 paginated reads, got {n}")
    return VerifierResult(status="PASS", reason="ok")
