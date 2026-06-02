"""Q35: Verifier for t03_patch_edit/t04_multiline.

Model uses a single patch for a 30-line block.
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
    target = worktree / "big_block.py"
    if not target.exists():
        return VerifierResult(status="FAIL", reason="big_block.py missing")
    used = any(
        (tc.get("function") or {}).get("name") == "patch"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use patch")
    text = target.read_text()
    if "def bar" not in text or "return 42" not in text:
        return VerifierResult(status="FAIL", reason="bar() not added", details={"file": text[:500]})
    return VerifierResult(status="PASS", reason="ok")
