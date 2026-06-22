"""Tests for fixture pollution guard CLI."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def test_fixture_integrity_ignores_untracked_by_default() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "hermesbench", "fixture-integrity"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Fixture integrity OK" in result.stderr
