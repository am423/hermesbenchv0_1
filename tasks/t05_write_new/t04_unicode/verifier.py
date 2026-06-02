"""Q35: Verifier for t05_write_new/t04_unicode.

Model writes file with non-ASCII content.
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
    target = worktree / "unicode.txt"
    if not target.exists():
        return VerifierResult(status="FAIL", reason="unicode.txt not created")
    text = target.read_text()
    if "日本語" not in text or "🚀" not in text:
        return VerifierResult(status="FAIL", reason="missing unicode")
    return VerifierResult(status="PASS", reason="ok")
