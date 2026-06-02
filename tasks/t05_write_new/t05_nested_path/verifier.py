"""Q35: Verifier for t05_write_new/t05_nested_path.

Model creates parent dirs and writes file.
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
    target = worktree / "nested" / "dir" / "file.txt"
    if not target.exists():
        return VerifierResult(status="FAIL", reason="nested file not created")
    if "nested content" not in target.read_text():
        return VerifierResult(status="FAIL", reason="wrong content")
    return VerifierResult(status="PASS", reason="ok")
