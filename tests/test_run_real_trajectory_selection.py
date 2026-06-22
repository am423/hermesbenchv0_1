"""Regression tests for real-run trajectory selection."""
from __future__ import annotations

import json
from pathlib import Path

from hermesbench.run_real import _select_trajectory_path, _trajectory_to_trace


def test_select_trajectory_prefers_success_samples(tmp_path: Path) -> None:
    worktree = tmp_path
    success = worktree / "trajectory_samples.jsonl"
    failed = worktree / "failed_trajectories.jsonl"
    success.write_text("{}\n", encoding="utf-8")
    failed.write_text("{}\n", encoding="utf-8")

    assert _select_trajectory_path(worktree) == success


def test_select_trajectory_uses_failed_when_success_missing(tmp_path: Path) -> None:
    failed = tmp_path / "failed_trajectories.jsonl"
    failed.write_text("{}\n", encoding="utf-8")

    assert _select_trajectory_path(tmp_path) == failed


def test_failed_trajectory_converts_to_trace(tmp_path: Path) -> None:
    failed = tmp_path / "failed_trajectories.jsonl"
    trace = tmp_path / "trace.jsonl"
    failed.write_text(
        json.dumps(
            {
                "timestamp": "2026-06-22T00:00:00",
                "conversations": [
                    {"from": "human", "value": "make a todo"},
                    {
                        "from": "gpt",
                        "value": '<tool_call>{"name":"todo","arguments":{"todos":[{"id":"a","content":"x","status":"pending"}]}}</tool_call>',
                    },
                    {
                        "from": "tool",
                        "value": json.dumps(
                            {
                                "tool_call_id": "call_0",
                                "name": "todo",
                                "content": {"todos": []},
                            }
                        ),
                    },
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    _trajectory_to_trace(failed, trace)

    rows = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    assert [r["role"] for r in rows] == ["user", "assistant", "tool"]
    assert rows[1]["tool_calls"][0]["function"]["name"] == "todo"
