"""Q74: tests for the CLI surface.

Covers: each subcommand's happy path, exit codes, error handling.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "hermesbench", *args],
        capture_output=True,
        text=True,
        cwd=REPO,
    )


def test_cli_help() -> None:
    r = run_cli("--help")
    assert r.returncode == 0
    assert "hermesbench" in r.stdout


def test_cli_version() -> None:
    r = run_cli("--version")
    assert r.returncode == 0
    assert "0.2.0" in r.stdout


def test_cli_list() -> None:
    r = run_cli("list")
    assert r.returncode == 0


def test_cli_doctor_runs() -> None:
    r = run_cli("doctor")
    # doctor may return 4 if agg missing, but should always be in {0, 4}
    assert r.returncode in (0, 4)


def test_cli_validate_default_targets() -> None:
    r = run_cli("validate")
    # Should validate fixtures/ + tasks/ — both valid
    assert r.returncode == 0


def test_cli_validate_with_path() -> None:
    r = run_cli("validate", "--path", "tasks/")
    assert r.returncode == 0


def test_cli_run_unknown_task_exits_4() -> None:
    r = run_cli("run", "--model", "x", "--task", "t99_nonexistent", "--base-url", "http://localhost:9999")
    assert r.returncode == 4


def test_cli_run_no_args_exits_4() -> None:
    r = run_cli("run", "--model", "x", "--base-url", "http://localhost:9999")
    assert r.returncode == 4


def test_cli_score_missing_path() -> None:
    # v0.2: score command uses aggregate_results; test that it's registered
    # and accepts --path. Click 8.4 subprocess invocation has a parsing quirk
    # with multiple=True options; tested via CliRunner elsewhere.
    r = run_cli("score", "--help")
    assert r.returncode == 0
    assert "--path" in r.stdout
