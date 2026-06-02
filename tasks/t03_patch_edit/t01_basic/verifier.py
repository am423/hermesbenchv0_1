"""Q35: Verifier for t03_patch_edit/t01_basic.

Model patches broken_divide.py with a ValueError guard.
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
    target = worktree / "broken_divide.py"
    if not target.exists():
        return VerifierResult(status="FAIL", reason="broken_divide.py missing")
    used = any(
        (tc.get("function") or {}).get("name") == "patch"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use patch")
    text = target.read_text()
    if "ValueError" not in text:
        return VerifierResult(status="FAIL", reason="ValueError not in patched file", details={"file": text[:300]})
    if not __import__("re").search(r"b\s*[!=]=\s*0(\.0)?", text):
        return VerifierResult(status="FAIL", reason="no zero-check found", details={"file": text[:300]})
    return VerifierResult(status="PASS", reason="patched with ValueError guard")
