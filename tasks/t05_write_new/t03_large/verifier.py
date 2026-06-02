"""Q35: Verifier for t05_write_new/t03_large.

Model writes 10000 lines.
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
    target = worktree / "big.txt"
    if not target.exists():
        return VerifierResult(status="FAIL", reason="big.txt not created")
    n = sum(1 for _ in target.open())
    if n < 9000:
        return VerifierResult(status="FAIL", reason=f"big.txt has only {n} lines")
    return VerifierResult(status="PASS", reason=f"big.txt has {n} lines")
