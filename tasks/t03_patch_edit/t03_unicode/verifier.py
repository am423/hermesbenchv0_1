"""Q35: Verifier for t03_patch_edit/t03_unicode.

Model patches with non-ASCII content.
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
    target = worktree / "hello.txt"
    if not target.exists():
        return VerifierResult(status="FAIL", reason="hello.txt missing")
    used = any(
        (tc.get("function") or {}).get("name") == "patch"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use patch")
    if "🌍" not in target.read_text():
        return VerifierResult(status="FAIL", reason="emoji not in file")
    return VerifierResult(status="PASS", reason="ok")
