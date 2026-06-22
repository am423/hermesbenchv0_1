"""Q35: Verifier for t04_search_grep/t04_regex.

Model uses search_files with a regex.
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


def _search_path_is_scoped(arguments: object, worktree: Path) -> bool:
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except Exception:
            return True
    if not isinstance(arguments, dict):
        return True
    raw_path = arguments.get("path", ".")
    if raw_path in (None, "", "."):
        return True
    path = Path(str(raw_path)).expanduser()
    if not path.is_absolute():
        return True
    try:
        path.resolve().relative_to(worktree.resolve())
        return True
    except ValueError:
        return False


def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = False
    for msg in trace:
        if msg.get("role") != "assistant":
            continue
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            if fn.get("name") != "search_files":
                continue
            used = True
            if not _search_path_is_scoped(fn.get("arguments", ""), worktree):
                return VerifierResult(
                    status="FAIL",
                    reason="search_files path escaped benchmark worktree",
                )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use search_files")
    return VerifierResult(status="PASS", reason="ok")
