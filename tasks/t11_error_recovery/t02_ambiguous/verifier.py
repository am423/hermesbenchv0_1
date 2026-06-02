"""Q35: Verifier for t11_error_recovery/t02_ambiguous.

Model uses both patch and read_file.
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
    used_patch = any(
        (tc.get("function") or {}).get("name") == "patch"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    used_read = any(
        (tc.get("function") or {}).get("name") == "read_file"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used_patch or not used_read:
        return VerifierResult(status="FAIL", reason="model did not use both patch and read_file")
    return VerifierResult(status="PASS", reason="ok")
