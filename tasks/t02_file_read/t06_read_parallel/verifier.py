"""Q35: Verifier for t02_file_read/t06_read_parallel.

Q61: model emits 3 read_file calls in one assistant turn (parallel).
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
    n_calls = 0
    n_turns = 0
    for msg in trace:
        if msg.get("role") == "assistant":
            tcs = msg.get("tool_calls") or []
            reads = [tc for tc in tcs if (tc.get("function") or {}).get("name") == "read_file"]
            if reads:
                n_turns += 1
                n_calls += len(reads)
    if n_calls < 3:
        return VerifierResult(status="FAIL", reason=f"expected >=3 read calls, got {n_calls}")
    rate = (n_calls - n_turns) / n_calls if n_calls else 0
    return VerifierResult(
        status="PASS", reason=f"parallel={n_calls} calls in {n_turns} turns (rate={rate:.0%})",
        details={"n_calls": n_calls, "n_turns": n_turns, "parallel_rate": rate},
    )
