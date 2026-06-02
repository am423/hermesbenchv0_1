"""Q35: Verifier for t02_file_read/t01_read_head.

Model reads add.py via read_file.
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
    saw = False
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
                    if isinstance(args, dict) and "add" in str(args.get("path", "")):
                        saw = True
    if not saw:
        return VerifierResult(status="FAIL", reason="model did not read add.py")
    return VerifierResult(status="PASS", reason="ok")
