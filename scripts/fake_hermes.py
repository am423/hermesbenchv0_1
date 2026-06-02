"""Fake hermes-agent: writes canned trace messages, then exits.

This is NOT a real hermes-agent. It's a stand-in for end-to-end
testing the hermesbench pipeline without needing a real LLM or the
hermes-agent checkout.

The fake "model" decides what to do based on the task prompt:
- If the prompt mentions "echo": write a trace where the model uses
  the terminal tool with `echo ...` and reports the output.
- If the prompt mentions "broken_divide": write a trace where the
  model patches the file.
- Otherwise: write a minimal "I read the file" trace.

This produces a real trace.jsonl in the worktree, which the
verifier then checks, which produces a real verifier_result.json,
which the scoring then summarizes.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path


def emit(role: str, content: str = "", tool_calls: list | None = None,
         reasoning: str = "", tool_call_id: str = "", tool_name: str = "",
         ts: float = 0.0, **extras) -> None:
    msg = {"role": role, "ts": ts}
    if content:
        msg["content"] = content
    if tool_calls:
        msg["tool_calls"] = tool_calls
    if reasoning:
        msg["reasoning_content"] = reasoning
    if tool_call_id:
        msg["tool_call_id"] = tool_call_id
    if tool_name:
        msg["name"] = tool_name
    msg.update(extras)
    print(json.dumps(msg), flush=True)


def make_tool_call(name: str, args: dict, call_id: str) -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": json.dumps(args),
        },
    }


def make_tool_result(call_id: str, name: str, content: str) -> dict:
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "content": f"[{name}] {content}",
        "ts": time.time(),
    }


def main() -> int:
    # Read the task prompt from stdin (the first line)
    prompt = sys.stdin.readline().strip()

    t = time.time()
    emit("system", content="You are hermes.", ts=t)
    emit("user", content=prompt, ts=t + 0.1)
    t += 0.2

    # Decide what to do based on the prompt
    worktree = Path(os.environ.get("HERMES_TMUX_WORKTREE", "."))
    if "echo" in prompt.lower():
        # Run echo via terminal
        emit("assistant", reasoning="I'll run the echo command.",
             tool_calls=[make_tool_call("terminal", {"command": "echo hello-hermesbench"}, "call_e1")],
             ts=t)
        emit("tool", tool_call_id="call_e1", tool_name="terminal",
             content="[terminal] hello-hermesbench", ts=t + 0.3)
        t += 0.4
        emit("assistant", content="Command output:\n```\nhello-hermesbench\n```",
             ts=t)

    elif "broken_divide" in prompt.lower():
        # Read the file, then patch it
        emit("assistant",
             reasoning="I need to read the file first, then add a zero check.",
             tool_calls=[make_tool_call("read_file", {"path": "broken_divide.py"}, "call_r1")],
             ts=t)
        emit("tool", tool_call_id="call_r1", tool_name="read_file",
             content="[read_file] read broken_divide.py (131 chars)", ts=t + 0.3)
        t += 0.4
        emit("assistant",
             tool_calls=[make_tool_call("patch", {
                 "path": "broken_divide.py",
                 "old_string": "    # Bug: no zero-division check\n    return a / b",
                 "new_string": "    if b == 0:\n        raise ValueError('division by zero')\n    return a / b",
             }, "call_p1")],
             ts=t)
        emit("tool", tool_call_id="call_p1", tool_name="patch",
             content="[patch] patched broken_divide.py", ts=t + 0.3)
        t += 0.4
        # Actually apply the patch to the worktree (we're running inside hermes's CWD)
        broken_path = worktree / "broken_divide.py"
        if broken_path.exists():
            text = broken_path.read_text()
            new_text = text.replace(
                "    # Bug: no zero-division check\n    return a / b",
                "    if b == 0:\n        raise ValueError('division by zero')\n    return a / b",
            )
            if new_text != text:
                broken_path.write_text(new_text)
        emit("assistant",
             content="I've added a zero-division check. The file now raises ValueError when b==0.",
             ts=t)

    elif "read" in prompt.lower() and ("add.py" in prompt or "read" in prompt):
        # Read a file
        emit("assistant",
             tool_calls=[make_tool_call("read_file", {"path": "add.py"}, "call_r1")],
             ts=t)
        emit("tool", tool_call_id="call_r1", tool_name="read_file",
             content="[read_file] def add(a, b): return a+b", ts=t + 0.3)
        t += 0.4
        # The fake hermes is a SUBPROCESS of the runner, not running
        # inside the tmux session, so it doesn't see the worktree CWD.
        # In a real hermes-agent, it WOULD be inside the tmux session.
        # For the fake, we emit the same trace shape.
        emit("assistant", content="add.py defines `add(a, b)` which returns a+b.",
             ts=t)

    else:
        # Default: just acknowledge
        emit("assistant", content=f"Acknowledged: {prompt[:200]}", ts=t)

    return 0


if __name__ == "__main__":
    sys.exit(main())
