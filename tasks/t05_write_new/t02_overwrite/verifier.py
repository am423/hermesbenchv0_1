"""Q35: Verifier for t05_write_new/t02_overwrite.

Model overwrites greeting.txt.
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
    target = worktree / "greeting.txt"
    if not target.exists():
        return VerifierResult(status="FAIL", reason="greeting.txt missing")
    if "Updated!" not in target.read_text():
        return VerifierResult(status="FAIL", reason="not overwritten")
    return VerifierResult(status="PASS", reason="ok")
