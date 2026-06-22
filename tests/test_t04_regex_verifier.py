"""Regression tests for t04_search_grep/t04_regex verifier scoping."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parent.parent / "tasks" / "t04_search_grep" / "t04_regex"


def _load_verifier():
    spec = importlib.util.spec_from_file_location("t04_regex_verifier", TASK_DIR / "verifier.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _trace_with_path(path: str) -> list[dict]:
    return [
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "type": "function",
                    "function": {
                        "name": "search_files",
                        "arguments": json.dumps({"pattern": "def", "path": path}),
                    },
                }
            ],
        }
    ]


def test_regex_verifier_rejects_absolute_path_outside_worktree(tmp_path: Path) -> None:
    mod = _load_verifier()
    result = mod.verify(tmp_path / "worktree", _trace_with_path("/tmp/outside"))
    assert result.status == "FAIL"
    assert "escaped" in result.reason


def test_regex_verifier_allows_relative_path(tmp_path: Path) -> None:
    mod = _load_verifier()
    result = mod.verify(tmp_path / "worktree", _trace_with_path("."))
    assert result.status == "PASS"


def test_regex_verifier_allows_absolute_path_inside_worktree(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    inside = worktree / "src"
    inside.mkdir(parents=True)
    mod = _load_verifier()
    result = mod.verify(worktree, _trace_with_path(str(inside)))
    assert result.status == "PASS"
