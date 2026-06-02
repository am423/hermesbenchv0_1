"""Template verifier — replace with your own logic.

Stdlib-only. Must return a VerifierResult.
"""
from __future__ import annotations

import json
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
    """Run the verification. Modify the body to check your task's outcome."""
    if not worktree.exists():
        return VerifierResult(status="FAIL", reason="worktree missing")

    # Example: check that the model created a file
    target = worktree / "expected_output.txt"
    if not target.exists():
        return VerifierResult(status="FAIL", reason=f"missing {target.name}")

    return VerifierResult(status="PASS", reason="ok", details={"size": target.stat().st_size})
