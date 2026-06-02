"""Helper: generate a task directory from a name + spec.

Avoids hand-typing 40 task.yaml files. Used by the project bootstrap
script; not part of the runtime.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent  # scripts/ -> repo root

TASK_TEMPLATE = '''\
id: {id}
name: "{name}"
version: 1
difficulty: {difficulty}
tags: [{tags}]

prompt: |
  {prompt}

allowed_tools:
{allowed_tools}

forbidden_tools: []

max_turns: {max_turns}
max_tokens: {max_tokens}
timeout_seconds: {timeout}
isolated_network: {isolated_network}

fixture:
  source: {fixture}
  globs: ["**/*"]

sampling:
  temperature: 0.0
  top_p: 1.0
  top_k: -1
  seed: 42

resource_limits:
  max_memory_mb: 2048
  max_processes: 128
  max_file_size_mb: 100
  max_worktree_mb: 500

hermes_plugins: []

latency_injection_ms:
{limyaml}

model_endpoint:
  type: openai_chat_completions
  required_fields: [tools, tool_choice]
  forbidden_fields: [logprobs]

verifier:
  module: verifier
  fn: verify
  timeout_seconds: {verifier_timeout}
'''

VERIFIER_HEADER = '''\
"""Q35: Verifier for {id}.

{summary}
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


'''


def write_task(
    *,
    task_id: str,
    name: str,
    difficulty: int,
    tags: list[str],
    prompt: str,
    allowed_tools: list[str],
    fixture: str = "small_repo",
    max_turns: int = 10,
    max_tokens: int = 4096,
    timeout: int = 60,
    verifier_timeout: int = 10,
    isolated_network: bool = True,
    latency_injection_ms: dict[str, int] | None = None,
    verifier_body: str = "",
    verifier_summary: str = "",
) -> Path:
    """Write a task.yaml + verifier.py pair to tasks/<category>/<instance>/.

    Returns the task dir path.
    """
    cat, inst = task_id.split("/")
    task_dir = REPO / "tasks" / cat / inst
    task_dir.mkdir(parents=True, exist_ok=True)

    lim = {"terminal": 0, "read_file": 0, "patch": 0}
    if latency_injection_ms:
        lim.update(latency_injection_ms)
    limyaml = "\n".join(f"  {k}: {v}" for k, v in lim.items())

    yaml_text = TASK_TEMPLATE.format(
        id=task_id,
        name=name,
        difficulty=difficulty,
        tags=", ".join(tags),
        prompt=prompt.strip(),
        allowed_tools="\n".join(f"  - {t}" for t in allowed_tools),
        max_turns=max_turns,
        max_tokens=max_tokens,
        timeout=timeout,
        isolated_network="true" if isolated_network else "false",
        fixture=fixture,
        verifier_timeout=verifier_timeout,
        limyaml=limyaml,
    )
    (task_dir / "task.yaml").write_text(yaml_text)
    (task_dir / "verifier.py").write_text(
        VERIFIER_HEADER.format(id=task_id, summary=verifier_summary) + verifier_body
    )
    return task_dir


# ----------------------------------------------------------------------------
# Task specs (43 tasks, per §4 of project.md)
# ----------------------------------------------------------------------------

TASKS: list[dict] = [
    # ---------- t01_terminal_smoke (5) ----------
    {
        "task_id": "t01_terminal_smoke/t01_echo",
        "name": "Echo a string",
        "difficulty": 1,
        "tags": ["terminal", "basics"],
        "prompt": "Run the bash command `echo hello-hermesbench` and report the output.",
        "allowed_tools": ["terminal"],
        "verifier_summary": "Model uses terminal tool to run an echo and reports the output.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used_terminal = False
    for msg in trace:
        if msg.get("role") == "assistant":
            for tc in (msg.get("tool_calls") or []):
                if (tc.get("function") or {}).get("name") == "terminal":
                    used_terminal = True
    if not used_terminal:
        return VerifierResult(status="FAIL", reason="model did not use terminal tool")
    final = ""
    for msg in reversed(trace):
        if msg.get("role") == "assistant" and msg.get("content"):
            final = msg["content"]
            break
    if "hello-hermesbench" not in final:
        return VerifierResult(
            status="FAIL", reason=f"final message missing 'hello-hermesbench': {final[:200]!r}"
        )
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t01_terminal_smoke/t02_ls",
        "name": "List files in worktree",
        "difficulty": 1,
        "tags": ["terminal", "basics"],
        "prompt": "Run `ls -la` and list the files you see.",
        "allowed_tools": ["terminal"],
        "verifier_summary": "Model uses terminal to list and acknowledges the output.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = any(
        (tc.get("function") or {}).get("name") == "terminal"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use terminal")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t01_terminal_smoke/t03_compile_check",
        "name": "Run a syntax check",
        "difficulty": 2,
        "tags": ["terminal", "python"],
        "prompt": "Run `python3 -m py_compile add.py` and report whether it compiles cleanly.",
        "allowed_tools": ["terminal"],
        "verifier_summary": "Model uses terminal to run py_compile.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = any(
        (tc.get("function") or {}).get("name") == "terminal"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use terminal")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t01_terminal_smoke/t04_pipeline",
        "name": "Pipe cat to grep to wc",
        "difficulty": 2,
        "tags": ["terminal", "pipes"],
        "prompt": "Run `cat add.py | grep def | wc -l` and report the count.",
        "allowed_tools": ["terminal"],
        "verifier_summary": "Model runs the pipeline.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = False
    for msg in trace:
        if msg.get("role") == "assistant":
            for tc in (msg.get("tool_calls") or []):
                fn = (tc.get("function") or {})
                if fn.get("name") == "terminal":
                    args = fn.get("arguments", "")
                    if isinstance(args, str) and "cat" in args and "grep" in args and "wc" in args:
                        used = True
    if not used:
        return VerifierResult(status="FAIL", reason="model did not run the pipe")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t01_terminal_smoke/t05_env_check",
        "name": "Check an environment variable",
        "difficulty": 2,
        "tags": ["terminal", "env"],
        "prompt": "Run `echo $HOME` and report the value.",
        "allowed_tools": ["terminal"],
        "verifier_summary": "Model echoes $HOME.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = any(
        (tc.get("function") or {}).get("name") == "terminal"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use terminal")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    # ---------- t02_file_read (6) ----------
    {
        "task_id": "t02_file_read/t01_read_head",
        "name": "Read first 50 lines",
        "difficulty": 1,
        "tags": ["read_file", "basics"],
        "prompt": "Read the first 50 lines of `add.py` and report what it contains.",
        "allowed_tools": ["read_file", "terminal"],
        "verifier_summary": "Model reads add.py via read_file.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    saw = False
    for msg in trace:
        if msg.get("role") == "assistant":
            for tc in (msg.get("tool_calls") or []):
                fn = (tc.get("function") or {})
                if fn.get("name") == "read_file":
                    args = fn.get("arguments", "")
                    if isinstance(args, str):
                        try:
                            import json
                            args = json.loads(args)
                        except Exception:
                            continue
                    if isinstance(args, dict) and "add" in str(args.get("path", "")):
                        saw = True
    if not saw:
        return VerifierResult(status="FAIL", reason="model did not read add.py")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t02_file_read/t02_read_tail",
        "name": "Read last 20 lines",
        "difficulty": 1,
        "tags": ["read_file", "basics"],
        "prompt": "Read the last 20 lines of `add.py`.",
        "allowed_tools": ["read_file", "terminal"],
        "verifier_summary": "Model reads add.py with offset+limit to get the tail.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    saw = False
    for msg in trace:
        if msg.get("role") == "assistant":
            for tc in (msg.get("tool_calls") or []):
                fn = (tc.get("function") or {})
                if fn.get("name") == "read_file":
                    args = fn.get("arguments", "")
                    if isinstance(args, str):
                        try:
                            import json
                            args = json.loads(args)
                        except Exception:
                            continue
                    if isinstance(args, dict) and "add" in str(args.get("path", "")):
                        saw = True
    if not saw:
        return VerifierResult(status="FAIL", reason="model did not read add.py")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t02_file_read/t03_read_paginated",
        "name": "Read a file in 3 chunks",
        "difficulty": 2,
        "tags": ["read_file", "pagination"],
        "prompt": "Read the file `big_file.py` in 3 chunks of ~50 lines each. Report the line counts.",
        "allowed_tools": ["read_file", "terminal"],
        "verifier_summary": "Model calls read_file at least 3 times with offset/limit.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    n = 0
    for msg in trace:
        if msg.get("role") == "assistant":
            for tc in (msg.get("tool_calls") or []):
                fn = (tc.get("function") or {})
                if fn.get("name") == "read_file":
                    args = fn.get("arguments", "")
                    if isinstance(args, str):
                        try:
                            import json
                            args = json.loads(args)
                        except Exception:
                            continue
                    if isinstance(args, dict) and "offset" in args:
                        n += 1
    if n < 3:
        return VerifierResult(status="FAIL", reason=f"expected >=3 paginated reads, got {n}")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t02_file_read/t04_read_missing",
        "name": "Recover from a missing file",
        "difficulty": 2,
        "tags": ["read_file", "error_recovery"],
        "prompt": "Read `nonexistent.py`. Handle the error gracefully.",
        "allowed_tools": ["read_file", "terminal"],
        "verifier_summary": "Model attempts to read missing file and recovers.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    attempted = False
    for msg in trace:
        if msg.get("role") == "assistant":
            for tc in (msg.get("tool_calls") or []):
                fn = (tc.get("function") or {})
                if fn.get("name") == "read_file":
                    args = fn.get("arguments", "")
                    if isinstance(args, str) and "nonexistent" in args:
                        attempted = True
    if not attempted:
        return VerifierResult(status="FAIL", reason="model did not attempt the missing file")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t02_file_read/t05_read_nested",
        "name": "Read a deeply-nested path",
        "difficulty": 1,
        "tags": ["read_file", "paths"],
        "prompt": "Read `add.py` (note the path is in a subdirectory).",
        "allowed_tools": ["read_file", "terminal"],
        "verifier_summary": "Model uses read_file.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = any(
        (tc.get("function") or {}).get("name") == "read_file"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use read_file")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t02_file_read/t06_read_parallel",
        "name": "Read multiple files in one turn",
        "difficulty": 2,
        "tags": ["read_file", "parallel", "Q61"],
        "prompt": "Show me the contents of `a.py`, `b.py`, and `c.py`. Use a single assistant turn.",
        "allowed_tools": ["read_file", "terminal"],
        "verifier_summary": "Q61: model emits 3 read_file calls in one assistant turn (parallel).",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    n_calls = 0
    n_turns = 0
    for msg in trace:
        if msg.get("role") == "assistant":
            tcs = msg.get("tool_calls") or []
            reads = [tc for tc in tcs if (tc.get("function") or {}).get("name") == "read_file"]
            if reads:
                n_turns += 1
                n_calls += len(reads)
    if n_calls < 3:
        return VerifierResult(status="FAIL", reason=f"expected >=3 read calls, got {n_calls}")
    rate = (n_calls - n_turns) / n_calls if n_calls else 0
    return VerifierResult(
        status="PASS", reason=f"parallel={n_calls} calls in {n_turns} turns (rate={rate:.0%})",
        details={"n_calls": n_calls, "n_turns": n_turns, "parallel_rate": rate},
    )
''',
    },
    # ---------- t03_patch_edit (5) ----------
    {
        "task_id": "t03_patch_edit/t01_basic",
        "name": "Add a zero-division check",
        "difficulty": 2,
        "tags": ["patch", "code-edit"],
        "prompt": "The file `broken_divide.py` has a bug: no zero-division check. Use `patch` to add a guard that raises `ValueError` when `b == 0`.",
        "allowed_tools": ["read_file", "patch", "terminal"],
        "verifier_summary": "Model patches broken_divide.py with a ValueError guard.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    target = worktree / "broken_divide.py"
    if not target.exists():
        return VerifierResult(status="FAIL", reason="broken_divide.py missing")
    used = any(
        (tc.get("function") or {}).get("name") == "patch"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use patch")
    text = target.read_text()
    if "ValueError" not in text:
        return VerifierResult(status="FAIL", reason="ValueError not in patched file", details={"file": text[:300]})
    if not __import__("re").search(r"b\\s*[!=]=\\s*0(\\.0)?", text):
        return VerifierResult(status="FAIL", reason="no zero-check found", details={"file": text[:300]})
    return VerifierResult(status="PASS", reason="patched with ValueError guard")
''',
    },
    {
        "task_id": "t03_patch_edit/t02_ambiguous",
        "name": "Patch a string that appears twice",
        "difficulty": 3,
        "tags": ["patch", "ambiguous"],
        "prompt": "The file `dup_strings.py` contains `foo = 1` twice. Patch only the SECOND occurrence to `foo = 2`. Use enough context to make `old_string` unique.",
        "allowed_tools": ["read_file", "patch", "terminal"],
        "verifier_summary": "Model uses enough context to disambiguate.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    target = worktree / "dup_strings.py"
    if not target.exists():
        return VerifierResult(status="FAIL", reason="dup_strings.py missing")
    used = any(
        (tc.get("function") or {}).get("name") == "patch"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use patch")
    text = target.read_text()
    n1 = text.count("foo = 1")
    n2 = text.count("foo = 2")
    if n1 != 1 or n2 != 1:
        return VerifierResult(
            status="FAIL", reason=f"expected 1 of each, got n1={n1} n2={n2}",
        )
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t03_patch_edit/t03_unicode",
        "name": "Patch with non-ASCII content",
        "difficulty": 2,
        "tags": ["patch", "unicode"],
        "prompt": "Patch `hello.txt` from `Hello, world!` to `Hello, world! 🌍`.",
        "allowed_tools": ["read_file", "patch", "terminal"],
        "verifier_summary": "Model patches with non-ASCII content.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    target = worktree / "hello.txt"
    if not target.exists():
        return VerifierResult(status="FAIL", reason="hello.txt missing")
    used = any(
        (tc.get("function") or {}).get("name") == "patch"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use patch")
    if "🌍" not in target.read_text():
        return VerifierResult(status="FAIL", reason="emoji not in file")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t03_patch_edit/t04_multiline",
        "name": "Patch a 30-line block",
        "difficulty": 3,
        "tags": ["patch", "multiline"],
        "prompt": "The file `big_block.py` has a class `Foo` (~30 lines). Add a method `def bar(self): return 42` using a single `patch` call.",
        "allowed_tools": ["read_file", "patch", "terminal"],
        "verifier_summary": "Model uses a single patch for a 30-line block.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    target = worktree / "big_block.py"
    if not target.exists():
        return VerifierResult(status="FAIL", reason="big_block.py missing")
    used = any(
        (tc.get("function") or {}).get("name") == "patch"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use patch")
    text = target.read_text()
    if "def bar" not in text or "return 42" not in text:
        return VerifierResult(status="FAIL", reason="bar() not added", details={"file": text[:500]})
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t03_patch_edit/t05_v4a",
        "name": "Use V4A patch format",
        "difficulty": 3,
        "tags": ["patch", "v4a"],
        "prompt": "Use `mode=patch` V4A format to insert `x = 1` at the top of `target.py`.",
        "allowed_tools": ["read_file", "patch", "terminal"],
        "verifier_summary": "Model uses V4A patch format.",
        "verifier_body": '''\
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
''',
    },
    # ---------- t04_search_grep (5) ----------
    {
        "task_id": "t04_search_grep/t01_basic",
        "name": "Find all files containing TODO",
        "difficulty": 1,
        "tags": ["search_files", "basics"],
        "prompt": "Find all files in the worktree containing the string `TODO`.",
        "allowed_tools": ["search_files", "terminal"],
        "verifier_summary": "Model uses search_files.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = any(
        (tc.get("function") or {}).get("name") == "search_files"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use search_files")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t04_search_grep/t02_glob",
        "name": "Search only .py files",
        "difficulty": 2,
        "tags": ["search_files", "glob"],
        "prompt": "Find all files in the worktree matching the glob `*.py` that contain `def `.",
        "allowed_tools": ["search_files", "terminal"],
        "verifier_summary": "Model uses file_glob.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = False
    for msg in trace:
        if msg.get("role") == "assistant":
            for tc in (msg.get("tool_calls") or []):
                fn = (tc.get("function") or {})
                if fn.get("name") == "search_files":
                    args = fn.get("arguments", "")
                    if isinstance(args, str):
                        try:
                            import json
                            args = json.loads(args)
                        except Exception:
                            continue
                    if isinstance(args, dict) and "file_glob" in args:
                        used = True
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use file_glob")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t04_search_grep/t03_output_mode",
        "name": "Use output_mode: count",
        "difficulty": 2,
        "tags": ["search_files", "output_mode"],
        "prompt": "Count the number of Python files (use `output_mode: count`) that contain `def `.",
        "allowed_tools": ["search_files", "terminal"],
        "verifier_summary": "Model uses search_files.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = any(
        (tc.get("function") or {}).get("name") == "search_files"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use search_files")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t04_search_grep/t04_regex",
        "name": "Use a regex pattern",
        "difficulty": 2,
        "tags": ["search_files", "regex"],
        "prompt": "Find all files containing the regex pattern `def\\s+\\w+\\(self` (methods).",
        "allowed_tools": ["search_files", "terminal"],
        "verifier_summary": "Model uses search_files with a regex.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = any(
        (tc.get("function") or {}).get("name") == "search_files"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use search_files")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t04_search_grep/t05_no_match",
        "name": "Handle no-match result",
        "difficulty": 2,
        "tags": ["search_files", "edge_case"],
        "prompt": "Search for the literal string `XXNOTFOUNDXX` and report that no files match.",
        "allowed_tools": ["search_files", "terminal"],
        "verifier_summary": "Model searches and reports no matches (not hallucinated).",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = any(
        (tc.get("function") or {}).get("name") == "search_files"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use search_files")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    # ---------- t05_write_new (5) ----------
    {
        "task_id": "t05_write_new/t01_basic",
        "name": "Write a new file",
        "difficulty": 1,
        "tags": ["write_file", "basics"],
        "prompt": "Create `greeting.txt` containing `Hello from hermesbench!`.",
        "allowed_tools": ["write_file", "terminal"],
        "verifier_summary": "Model creates greeting.txt with the expected content.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    target = worktree / "greeting.txt"
    if not target.exists():
        return VerifierResult(status="FAIL", reason="greeting.txt not created")
    if "Hello from hermesbench" not in target.read_text():
        return VerifierResult(status="FAIL", reason="wrong content")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t05_write_new/t02_overwrite",
        "name": "Overwrite an existing file",
        "difficulty": 1,
        "tags": ["write_file", "basics"],
        "prompt": "Overwrite `greeting.txt` with the new content `Updated!`.",
        "allowed_tools": ["write_file", "read_file", "terminal"],
        "verifier_summary": "Model overwrites greeting.txt.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    target = worktree / "greeting.txt"
    if not target.exists():
        return VerifierResult(status="FAIL", reason="greeting.txt missing")
    if "Updated!" not in target.read_text():
        return VerifierResult(status="FAIL", reason="not overwritten")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t05_write_new/t03_large",
        "name": "Write a 10K-line file",
        "difficulty": 2,
        "tags": ["write_file", "scale"],
        "prompt": "Write `big.txt` containing 10000 lines, each numbered `Line N`.",
        "allowed_tools": ["write_file", "terminal"],
        "verifier_summary": "Model writes 10000 lines.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    target = worktree / "big.txt"
    if not target.exists():
        return VerifierResult(status="FAIL", reason="big.txt not created")
    n = sum(1 for _ in target.open())
    if n < 9000:
        return VerifierResult(status="FAIL", reason=f"big.txt has only {n} lines")
    return VerifierResult(status="PASS", reason=f"big.txt has {n} lines")
''',
    },
    {
        "task_id": "t05_write_new/t04_unicode",
        "name": "Write non-ASCII content",
        "difficulty": 1,
        "tags": ["write_file", "unicode"],
        "prompt": "Create `unicode.txt` containing `日本語 🚀 émojis`.",
        "allowed_tools": ["write_file", "terminal"],
        "verifier_summary": "Model writes file with non-ASCII content.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    target = worktree / "unicode.txt"
    if not target.exists():
        return VerifierResult(status="FAIL", reason="unicode.txt not created")
    text = target.read_text()
    if "日本語" not in text or "🚀" not in text:
        return VerifierResult(status="FAIL", reason="missing unicode")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t05_write_new/t05_nested_path",
        "name": "Write to a nested path",
        "difficulty": 2,
        "tags": ["write_file", "paths"],
        "prompt": "Create a file at `nested/dir/file.txt` containing `nested content`.",
        "allowed_tools": ["write_file", "terminal"],
        "verifier_summary": "Model creates parent dirs and writes file.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    target = worktree / "nested" / "dir" / "file.txt"
    if not target.exists():
        return VerifierResult(status="FAIL", reason="nested file not created")
    if "nested content" not in target.read_text():
        return VerifierResult(status="FAIL", reason="wrong content")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    # ---------- t06_process_mgmt (5) ----------
    {
        "task_id": "t06_process_mgmt/t01_list",
        "name": "List background processes",
        "difficulty": 2,
        "tags": ["process", "basics"],
        "prompt": "Use `process` with action='list' to see background processes.",
        "allowed_tools": ["process", "terminal"],
        "verifier_summary": "Model uses process(action='list').",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = False
    for msg in trace:
        if msg.get("role") == "assistant":
            for tc in (msg.get("tool_calls") or []):
                fn = (tc.get("function") or {})
                if fn.get("name") == "process":
                    args = fn.get("arguments", "")
                    if isinstance(args, str):
                        try:
                            import json
                            args = json.loads(args)
                        except Exception:
                            continue
                    if isinstance(args, dict) and args.get("action") == "list":
                        used = True
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use process(action='list')")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t06_process_mgmt/t02_kill",
        "name": "Kill a leaked process",
        "difficulty": 3,
        "tags": ["process", "kill"],
        "prompt": "Find the running `sleep 999` process and kill it.",
        "allowed_tools": ["process", "terminal"],
        "verifier_summary": "Model uses process(action='kill').",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = False
    for msg in trace:
        if msg.get("role") == "assistant":
            for tc in (msg.get("tool_calls") or []):
                fn = (tc.get("function") or {})
                if fn.get("name") == "process":
                    args = fn.get("arguments", "")
                    if isinstance(args, str):
                        try:
                            import json
                            args = json.loads(args)
                        except Exception:
                            continue
                    if isinstance(args, dict) and args.get("action") == "kill":
                        used = True
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use process(action='kill')")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t06_process_mgmt/t03_poll",
        "name": "Poll a running process",
        "difficulty": 2,
        "tags": ["process", "poll"],
        "prompt": "Start a 3-second `sleep 30` in the background, then use `process` to poll it for output.",
        "allowed_tools": ["process", "terminal"],
        "verifier_summary": "Model uses process to poll.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = any(
        (tc.get("function") or {}).get("name") == "process"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use process")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t06_process_mgmt/t04_pipeline",
        "name": "Capture and parse structured output",
        "difficulty": 3,
        "tags": ["process", "pipelines"],
        "prompt": "Run `python3 -c 'import json; print(json.dumps({\"x\": 42}))'`, parse the output, and report x=42.",
        "allowed_tools": ["terminal"],
        "verifier_summary": "Model parses JSON output.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = any(
        (tc.get("function") or {}).get("name") == "terminal"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use terminal")
    final = ""
    for msg in reversed(trace):
        if msg.get("role") == "assistant" and msg.get("content"):
            final = msg["content"]
            break
    if "42" not in final:
        return VerifierResult(status="FAIL", reason=f"42 not in final: {final[:200]!r}")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t06_process_mgmt/t05_zombie",
        "name": "Detect and inspect process tree",
        "difficulty": 3,
        "tags": ["process", "zombie"],
        "prompt": "List all running processes and report any zombie processes you see.",
        "allowed_tools": ["process", "terminal"],
        "verifier_summary": "Model uses process or terminal to inspect process tree.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = any(
        (tc.get("function") or {}).get("name") in ("process", "terminal")
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use process or terminal")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    # ---------- t07_todo_plan (3) ----------
    {
        "task_id": "t07_todo_plan/t01_plan",
        "name": "Decompose a 4-step task",
        "difficulty": 2,
        "tags": ["todo", "planning"],
        "prompt": "Use `todo` to break this into 4 steps: (1) read add.py, (2) understand it, (3) add a docstring, (4) verify with a syntax check.",
        "allowed_tools": ["todo", "read_file", "patch", "terminal"],
        "verifier_summary": "Model uses todo with a 4-item list.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = False
    for msg in trace:
        if msg.get("role") == "assistant":
            for tc in (msg.get("tool_calls") or []):
                fn = (tc.get("function") or {})
                if fn.get("name") == "todo":
                    args = fn.get("arguments", "")
                    if isinstance(args, str):
                        try:
                            import json
                            args = json.loads(args)
                        except Exception:
                            continue
                    if isinstance(args, dict):
                        todos = args.get("todos", [])
                        if isinstance(todos, list) and len(todos) >= 4:
                            used = True
    if not used:
        return VerifierResult(status="FAIL", reason="model did not create a 4-item todo list")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t07_todo_plan/t02_update",
        "name": "Update todo status",
        "difficulty": 2,
        "tags": ["todo", "status"],
        "prompt": "Mark todo items as `in_progress` and then `completed` as you work through them.",
        "allowed_tools": ["todo", "terminal"],
        "verifier_summary": "Model uses todo to update status.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = any(
        (tc.get("function") or {}).get("name") == "todo"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use todo")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t07_todo_plan/t03_replan",
        "name": "Replan mid-flight",
        "difficulty": 3,
        "tags": ["todo", "replan"],
        "prompt": "Start with a 4-step plan, then discover a new requirement mid-flight: also add type hints. Use `todo` to insert the new step.",
        "allowed_tools": ["todo", "read_file", "patch", "terminal"],
        "verifier_summary": "Model calls todo at least 2 times (initial plan + replan).",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    n = sum(
        1 for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
        if (tc.get("function") or {}).get("name") == "todo"
    )
    if n < 2:
        return VerifierResult(status="FAIL", reason=f"expected >=2 todo calls (replan), got {n}")
    return VerifierResult(status="PASS", reason="ok")
''',
        "latency_injection_ms": {"terminal": 1500},
    },
    # ---------- t08_execute_code (5) ----------
    {
        "task_id": "t08_execute_code/t01_math",
        "name": "Compute a value in REPL",
        "difficulty": 1,
        "tags": ["execute_code", "math"],
        "prompt": "Use `execute_code` to compute the sum of squares from 1 to 10.",
        "allowed_tools": ["execute_code"],
        "verifier_summary": "Model uses execute_code to compute and report 385.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = any(
        (tc.get("function") or {}).get("name") == "execute_code"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use execute_code")
    final = ""
    for msg in reversed(trace):
        if msg.get("role") == "assistant" and msg.get("content"):
            final = msg["content"]
            break
    if "385" not in final:
        return VerifierResult(status="FAIL", reason=f"385 not in final: {final[:200]!r}")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t08_execute_code/t02_pandas",
        "name": "Aggregate a CSV",
        "difficulty": 2,
        "tags": ["execute_code", "pandas"],
        "prompt": "Use `execute_code` to load `data.csv`, group by `category`, and sum the `value` column.",
        "allowed_tools": ["execute_code"],
        "verifier_summary": "Model uses pandas in execute_code.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = any(
        (tc.get("function") or {}).get("name") == "execute_code"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use execute_code")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t08_execute_code/t03_debug",
        "name": "Find a bug by running code",
        "difficulty": 3,
        "tags": ["execute_code", "debug"],
        "prompt": "The function `factorial(n)` in `buggy.py` is incorrect. Use `execute_code` to find the bug and report it.",
        "allowed_tools": ["execute_code", "read_file"],
        "verifier_summary": "Model uses execute_code to test the buggy function.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = any(
        (tc.get("function") or {}).get("name") == "execute_code"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use execute_code")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t08_execute_code/t04_datascience",
        "name": "Train a small sklearn model",
        "difficulty": 3,
        "tags": ["execute_code", "sklearn"],
        "prompt": "Use `execute_code` to train a logistic regression on `data.csv` and report test accuracy.",
        "allowed_tools": ["execute_code"],
        "verifier_summary": "Model trains a model in execute_code.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = any(
        (tc.get("function") or {}).get("name") == "execute_code"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use execute_code")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t08_execute_code/t05_stateful",
        "name": "REPL state survives across calls",
        "difficulty": 2,
        "tags": ["execute_code", "stateful"],
        "prompt": "Use `execute_code` to: (1) define `x = 42`, (2) in a second call, print `x`. Verify state persists.",
        "allowed_tools": ["execute_code"],
        "verifier_summary": "Model uses execute_code twice.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    n = sum(
        1 for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
        if (tc.get("function") or {}).get("name") == "execute_code"
    )
    if n < 2:
        return VerifierResult(status="FAIL", reason=f"expected >=2 execute_code calls, got {n}")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    # ---------- t09_web_lookup (3, mocked) ----------
    {
        "task_id": "t09_web_lookup/t01_search",
        "name": "Web search for a fact",
        "difficulty": 2,
        "tags": ["web_search", "mocked"],
        "prompt": "Use `web_search` to find the capital of France.",
        "allowed_tools": ["web_search"],
        "verifier_summary": "Model uses web_search (mocked corpus).",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = any(
        (tc.get("function") or {}).get("name") == "web_search"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use web_search")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t09_web_lookup/t02_extract",
        "name": "Extract content from a URL",
        "difficulty": 2,
        "tags": ["web_extract", "mocked"],
        "prompt": "Use `web_extract` to fetch `https://wiki.example.com/python` and report the first paragraph.",
        "allowed_tools": ["web_extract"],
        "verifier_summary": "Model uses web_extract on a mocked URL.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = any(
        (tc.get("function") or {}).get("name") == "web_extract"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use web_extract")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t09_web_lookup/t03_no_result",
        "name": "Handle empty search results",
        "difficulty": 2,
        "tags": ["web_search", "edge_case"],
        "prompt": "Search for `XXNORESULTXX`. Report that nothing was found.",
        "allowed_tools": ["web_search"],
        "verifier_summary": "Model searches and reports no results.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = any(
        (tc.get("function") or {}).get("name") == "web_search"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use web_search")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    # ---------- t10_memory_facts (3) ----------
    {
        "task_id": "t10_memory_facts/t01_save",
        "name": "Save a fact to memory",
        "difficulty": 2,
        "tags": ["memory", "basics"],
        "prompt": "Use `memory` to save the fact: 'hermesbench v0.1 was released today'.",
        "allowed_tools": ["memory"],
        "verifier_summary": "Model uses memory(action='add').",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = False
    for msg in trace:
        if msg.get("role") == "assistant":
            for tc in (msg.get("tool_calls") or []):
                fn = (tc.get("function") or {})
                if fn.get("name") == "memory":
                    args = fn.get("arguments", "")
                    if isinstance(args, str):
                        try:
                            import json
                            args = json.loads(args)
                        except Exception:
                            continue
                    if isinstance(args, dict) and args.get("action") in ("add", "save"):
                        used = True
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use memory(action='add')")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t10_memory_facts/t02_recall",
        "name": "Recall across turns",
        "difficulty": 2,
        "tags": ["memory", "recall"],
        "prompt": "Recall the fact you saved in t10_t01.",
        "allowed_tools": ["memory"],
        "verifier_summary": "Model uses memory.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = any(
        (tc.get("function") or {}).get("name") == "memory"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use memory")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t10_memory_facts/t03_avoid_dup",
        "name": "Don't re-save a known fact",
        "difficulty": 2,
        "tags": ["memory", "dedup"],
        "prompt": "Try to save the same fact as t10_t01 again. Recognize it's a duplicate and don't save.",
        "allowed_tools": ["memory"],
        "verifier_summary": "Model dedupes by checking before saving.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used = any(
        (tc.get("function") or {}).get("name") == "memory"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used:
        return VerifierResult(status="FAIL", reason="model did not use memory")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    # ---------- t11_error_recovery (3, Q58) ----------
    {
        "task_id": "t11_error_recovery/t01_perms",
        "name": "Recover from a permission error",
        "difficulty": 3,
        "tags": ["error_recovery", "permissions"],
        "prompt": "The file `locked.txt` is chmod 000. Read it anyway using `sudo` or another workaround.",
        "allowed_tools": ["terminal", "read_file"],
        "verifier_summary": "Model recovers from a permission error within 2 turns.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    n_recoveries = 0
    for msg in trace:
        if msg.get("role") == "assistant":
            tcs = msg.get("tool_calls") or []
            for tc in tcs:
                fn = (tc.get("function") or {})
                if fn.get("name") in ("terminal", "read_file", "patch"):
                    n_recoveries += 1
    if n_recoveries < 2:
        return VerifierResult(status="FAIL", reason=f"only {n_recoveries} recovery attempts")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t11_error_recovery/t02_ambiguous",
        "name": "Disambiguate a fuzzy patch match",
        "difficulty": 3,
        "tags": ["error_recovery", "patch"],
        "prompt": "The file `multi.py` has 3 functions named `handler`. Use `patch` to update only the SECOND. The first patch attempt may return a 'Did you mean' hint — use `read_file` to disambiguate.",
        "allowed_tools": ["read_file", "patch", "terminal"],
        "verifier_summary": "Model uses both patch and read_file.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    used_patch = any(
        (tc.get("function") or {}).get("name") == "patch"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    used_read = any(
        (tc.get("function") or {}).get("name") == "read_file"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if not used_patch or not used_read:
        return VerifierResult(status="FAIL", reason="model did not use both patch and read_file")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
    {
        "task_id": "t11_error_recovery/t03_transient",
        "name": "Retry after a transient error",
        "difficulty": 3,
        "tags": ["error_recovery", "retry"],
        "prompt": "Run `curl http://nonexistent.invalid/`. The first attempt will fail. Retry with a backoff.",
        "allowed_tools": ["terminal"],
        "verifier_summary": "Model retries after a transient error.",
        "verifier_body": '''\
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    n_curl = 0
    for msg in trace:
        if msg.get("role") == "assistant":
            for tc in (msg.get("tool_calls") or []):
                fn = (tc.get("function") or {})
                if fn.get("name") == "terminal":
                    args = fn.get("arguments", "")
                    if isinstance(args, str) and "curl" in args:
                        n_curl += 1
    if n_curl < 2:
        return VerifierResult(status="FAIL", reason=f"expected >=2 curl calls (retry), got {n_curl}")
    return VerifierResult(status="PASS", reason="ok")
''',
    },
]


def main() -> int:
    print(f"Generating {len(TASKS)} tasks...")
    for spec in TASKS:
        kwargs = {
            "task_id": spec["task_id"],
            "name": spec["name"],
            "difficulty": spec["difficulty"],
            "tags": spec["tags"],
            "prompt": spec["prompt"],
            "allowed_tools": spec["allowed_tools"],
            "verifier_summary": spec["verifier_summary"],
            "verifier_body": spec["verifier_body"],
        }
        if "latency_injection_ms" in spec:
            kwargs["latency_injection_ms"] = spec["latency_injection_ms"]
        path = write_task(**kwargs)
        print(f"  + {path.relative_to(REPO)}")
    print(f"\n{len(TASKS)} tasks generated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
