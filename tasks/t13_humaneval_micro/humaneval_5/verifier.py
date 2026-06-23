"""HumanEval micro verifier for hermes-bench task dirs."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class VerifierResult:
    status: Literal["PASS", "FAIL", "SKIPPED", "BUDGET_EXCEEDED", "VERIFIER_ERROR"]
    score: float = 1.0
    reason: str = ""
    details: dict = field(default_factory=dict)


def _extract_python_completion(text: str) -> str:
    if not text:
        return ""
    blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if blocks:
        return blocks[-1].strip()
    return text.strip()


def _prompt_imports(prompt: str) -> str:
    """Return top-level import lines from a HumanEval prompt.

    Models are asked to reply with a full solution, but many omit imports that
    are already visible in the prompt (for example ``from typing import List``).
    The verifier should judge the solution logic, not fail a valid function on
    a missing annotation import supplied by the benchmark prompt.
    """

    imports: list[str] = []
    for line in prompt.splitlines():
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            imports.append(line)
            continue
        if stripped.startswith("def "):
            break
    return "\n".join(imports)


def _text_from_trace(trace: list[dict]) -> str:
    parts: list[str] = []
    for msg in trace:
        if msg.get("role") != "assistant":
            continue
        for key in ("content", "reasoning", "reasoning_content"):
            value = msg.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value)
    return "\n".join(parts)


def _run_humaneval_check(
    prompt: str,
    completion: str,
    test: str,
    entry_point: str,
    timeout_s: int = 15,
) -> tuple[bool, str]:
    body = _extract_python_completion(completion)
    if "def " in body:
        imports = _prompt_imports(prompt)
        program = f"{imports}\n\n{body}" if imports and imports not in body else body
    else:
        program = prompt + body
    script = f"""import sys
{program}
{test}
check({entry_point})
print("OK")
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as handle:
        handle.write(script)
        path = handle.name
    try:
        result = subprocess.run(
            [sys.executable, path],
            capture_output=True,
            text=True,
            timeout=timeout_s,
        )
        if result.returncode == 0 and "OK" in result.stdout:
            return True, "ok"
        err = (result.stderr or result.stdout or "").strip()[:500]
        return False, err or f"exit {result.returncode}"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    finally:
        Path(path).unlink(missing_ok=True)


def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    prob_path = worktree / "humaneval.json"
    if not prob_path.is_file():
        return VerifierResult(status="VERIFIER_ERROR", reason="missing humaneval.json")
    prob = json.loads(prob_path.read_text(encoding="utf-8"))
    ok, reason = _run_humaneval_check(
        prob["prompt"], _text_from_trace(trace), prob["test"], prob["entry_point"]
    )
    if ok:
        return VerifierResult(status="PASS", reason="ok")
    return VerifierResult(status="FAIL", reason=reason)
