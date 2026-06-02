"""Hermes-agent invocation: find the checkout, spawn the subprocess.

Q22: resolution order is $HERMES_AGENT_PATH > ./hermes-agent/ >
~/.hermes/hermes-agent/ > `import hermes_agent`.
Q50: record the hermes git SHA in meta.json.
Q57: smoke-test the model endpoint before kicking off the suite.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def find_hermes_agent() -> Path:
    """Resolve the hermes-agent checkout per Q22."""
    env = os.environ.get("HERMES_AGENT_PATH")
    if env:
        p = Path(env).expanduser().resolve()
        if p.exists():
            return p
    cwd = Path.cwd()
    candidates = [
        cwd / "hermes-agent",
        Path.home() / ".hermes" / "hermes-agent",
    ]
    for c in candidates:
        if c.exists():
            return c.resolve()
    # Fall back: try `import hermes_agent`
    try:
        import hermes_agent  # type: ignore[import-not-found]

        return Path(hermes_agent.__file__).parent.resolve()
    except ImportError:
        pass
    raise FileNotFoundError(
        "Could not find hermes-agent. Set $HERMES_AGENT_PATH or install hermes_agent."
    )


def get_hermes_sha(hermes_path: Path) -> str:
    """Return the current git SHA of the hermes-agent checkout."""
    try:
        r = subprocess.run(
            ["git", "-C", str(hermes_path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        out = r.stdout.strip()
        return out if out else "unknown"
    except Exception:
        return "unknown"


def get_hermes_version(hermes_path: Path) -> str:
    """Return the hermes-agent package version."""
    try:
        import hermes_agent  # type: ignore[import-not-found]

        return getattr(hermes_agent, "__version__", "unknown")
    except ImportError:
        return "unknown"


def smoke_test_endpoint(base_url: str, model: str, expected: dict) -> tuple[bool, str]:
    """Q57: send a 1-token request to verify the endpoint contract.

    Returns (ok, message). ok=False if the response shape is wrong.
    """
    try:
        import urllib.request

        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/chat/completions",
            data=json.dumps(
                {
                    "model": model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1,
                    "stream": False,
                }
            ).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read())
        # Check required fields
        for field in expected.get("required_fields", []):
            if field == "tools" and "tools" not in resp:
                # The response may not include tools; send a second request with tools
                req2 = urllib.request.Request(
                    f"{base_url.rstrip('/')}/chat/completions",
                    data=json.dumps(
                        {
                            "model": model,
                            "messages": [{"role": "user", "content": "hi"}],
                            "max_tokens": 1,
                            "tools": [
                                {
                                    "type": "function",
                                    "function": {
                                        "name": "noop",
                                        "description": "noop",
                                        "parameters": {},
                                    },
                                }
                            ],
                        }
                    ).encode(),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req2, timeout=10) as r2:
                    resp2 = json.loads(r2.read())
                if "choices" not in resp2:
                    return False, f"endpoint did not return choices for tool call"
                return True, "ok"
        if "choices" not in resp:
            return False, f"endpoint response missing 'choices': keys={list(resp.keys())}"
        return True, "ok"
    except Exception as e:
        return False, f"endpoint smoke test failed: {type(e).__name__}: {e}"


def spawn_hermes(
    *,
    hermes_path: Path,
    task_prompt: str,
    worktree: Path,
    isolated_home: Path,
    cast_path: Path,
    model: str,
    base_url: str,
    env_overrides: dict[str, str],
    timeout_seconds: int = 180,
) -> subprocess.Popen:
    """Spawn hermes-agent as a subprocess and feed the task prompt.

    Q53: --line-buffered, Q54: DISABLED_TOOLSETS from plugin allowlist.
    """
    env = {
        **os.environ,
        "TERMINAL_ENV": "tmux_isolated",
        "HERMES_TMUX_SESSION": f"hb-{worktree.name}",
        "HERMES_TMUX_WORKTREE": str(worktree),
        "HERMES_TMUX_HOME": str(isolated_home),
        "HERMES_TMUX_CAST_PATH": str(cast_path),
        "OPENAI_BASE_URL": base_url,
        "OPENAI_MODEL": model,
        "HERMES_QUIET": "1",
        "HERMES_SAVE_TRAJECTORY": "1",
        "HERMES_TRAJECTORY_PATH": str(worktree / "trace.jsonl"),
        "PYTHONUNBUFFERED": "1",
        **env_overrides,
    }
    cmd = [
        "python",
        "-u",
        "-m",
        "hermes_agent",
        "--print-mode",
        "jsonl",
        "--no-tui",
        "--line-buffered",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=hermes_path,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=0,
    )
    assert proc.stdin is not None
    proc.stdin.write(task_prompt + "\n")
    proc.stdin.flush()
    return proc
