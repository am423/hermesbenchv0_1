"""Q35: Verifier for t09_web_lookup/t02_extract.

Model uses web_extract on a mocked URL.
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
        (tc.get("function") or {}).get("name") == "web_extract"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use web_extract")
    return VerifierResult(status="PASS", reason="ok")
