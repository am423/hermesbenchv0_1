"""Q35: Verifier for t03_patch_edit/t05_v4a.

Model uses V4A patch format.
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
    target = worktree / "target.py"
    if not target.exists():
        return VerifierResult(status="FAIL", reason="target.py missing")
    used_v4a = False
    for msg in trace:
        if msg.get("role") == "assistant":
            for tc in (msg.get("tool_calls") or []):
                fn = (tc.get("function") or {})
                if fn.get("name") == "patch":
                    args = fn.get("arguments", "")
                    if isinstance(args, str):
                        try:
                            import json
                            args = json.loads(args)
                        except Exception:
                            continue
                    if isinstance(args, dict):
                        if "patch" in str(args.get("mode", "")) and "*** Begin Patch" in str(args.get("patch", "")):
                            used_v4a = True
    if not used_v4a:
        return VerifierResult(status="FAIL", reason="model did not use V4A format")
    if "x = 1" not in target.read_text():
        return VerifierResult(status="FAIL", reason="x=1 not in file")
    return VerifierResult(status="PASS", reason="ok")
