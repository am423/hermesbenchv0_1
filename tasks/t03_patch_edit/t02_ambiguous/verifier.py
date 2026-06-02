"""Q35: Verifier for t03_patch_edit/t02_ambiguous.

Model uses enough context to disambiguate.
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
    target = worktree / "dup_strings.py"
    if not target.exists():
        return VerifierResult(status="FAIL", reason="dup_strings.py missing")
    used = any(
        (tc.get("function") or {}).get("name") == "patch"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use patch")
    text = target.read_text()
    n1 = text.count("foo = 1")
    n2 = text.count("foo = 2")
    if n1 != 1 or n2 != 1:
        return VerifierResult(
            status="FAIL", reason=f"expected 1 of each, got n1={n1} n2={n2}",
        )
    return VerifierResult(status="PASS", reason="ok")
