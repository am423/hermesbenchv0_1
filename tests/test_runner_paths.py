"""Regression tests for output-root plumbing."""
from __future__ import annotations

from pathlib import Path

from hermesbench.runner import run_task
from hermesbench.types import TaskSpec

REPO = Path(__file__).resolve().parent.parent


def test_run_task_dry_run_uses_custom_traces_root(tmp_path: Path) -> None:
    spec = TaskSpec.from_yaml(REPO / "tasks" / "t01_terminal_smoke" / "t01_echo" / "task.yaml")
    results_root = tmp_path / "out"
    traces_root = tmp_path / "out" / "traces"

    result = run_task(
        spec,
        model="unit-model",
        base_url="http://127.0.0.1:9/v1",
        results_root=results_root,
        traces_root=traces_root,
        dry_run=True,
    )

    assert result.verifier_result.status.value == "SKIPPED"
    assert result.trace_path.is_relative_to(traces_root)
    assert result.worktree.is_relative_to(traces_root)
    assert result.worktree.exists()
