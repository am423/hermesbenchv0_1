from __future__ import annotations

import subprocess
from pathlib import Path

from hermesbench.run_real import _detect_infra_error


def test_successful_agent_exit_with_api_failure_log_is_infra(tmp_path: Path) -> None:
    log_path = tmp_path / "run_agent.log"
    log_path.write_text(
        "API call failed after 3 retries: Connection error.\n"
        "FINAL RESPONSE: API call failed after 3 retries: Connection error.\n",
        encoding="utf-8",
    )

    reason = _detect_infra_error(
        completed=subprocess.CompletedProcess(["run_agent.py"], 0, "", ""),
        log_path=log_path,
        selected_trajectory_path=None,
    )

    assert reason is not None
    assert "API call failed after" in reason or "Connection error" in reason
