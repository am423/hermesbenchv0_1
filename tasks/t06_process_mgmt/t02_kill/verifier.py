"""Q35: Verifier for t06_process_mgmt/t02_kill.

Model uses process(action='kill').
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
                if fn.get("name") == "process":
                    args = fn.get("arguments", "")
                    if isinstance(args, str):
                        try:
                            import json
                            args = json.loads(args)
                        except Exception:
                            continue
                    if isinstance(args, dict) and args.get("action") == "kill":
                        used = True
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use process(action='kill')")
    return VerifierResult(status="PASS", reason="ok")
