"""Fake OpenAI-compatible chat-completions server for hermesbench testing.

Listens on localhost:8080, returns canned responses that exercise
the most common hermes tool calls. NOT for production use.

Run with: python -m scripts.fake_model_server
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Make hermesbench importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Per-conversation state (file_path -> contents)
_FIXTURES: dict[str, str] = {
    "broken_divide.py": """\
def divide(a: float, b: float) -> float:
    # Bug: no zero-division check
    return a / b
""",
    "add.py": """\
def add(a: int, b: int) -> int:
    return a + b
""",
}


def _make_read_response(file_path: str) -> dict:
    if file_path in _FIXTURES:
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": f"I've read {file_path}. It contains: {_FIXTURES[file_path][:200]}",
                        "tool_calls": [],
                    }
                }
            ]
        }
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": f"File not found: {file_path}",
                    "tool_calls": [],
                }
            }
        ]
    }


def _make_patch_response(old: str, new: str) -> dict:
    """Just acknowledge."""
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": f"Patched. Replaced:\n{old[:50]}\nwith:\n{new[:50]}",
                    "tool_calls": [],
                }
            }
        ]
    }


def _make_echo_response(user_msg: str) -> dict:
    """For terminal-echo tasks, simulate executing the command and return its output."""
    if "echo" in user_msg:
        # Find what to echo
        import re

        m = re.search(r"echo\s+(.+?)(?:\n|$)", user_msg)
        text = m.group(1).strip().strip("'\"") if m else "hello-hermesbench"
        output = f"{text}\n"
    else:
        output = "command executed\n"
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": f"Command output:\n```\n{output}```",
                    "tool_calls": [],
                }
            }
        ]
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        # Quiet logging
        pass

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode()
        try:
            req = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400)
            return

        # Echo back a canned response
        user_msg = ""
        for m in req.get("messages", []):
            if m.get("role") == "user":
                user_msg += m.get("content", "") + "\n"

        if "echo" in user_msg:
            resp = _make_echo_response(user_msg)
        elif "broken_divide" in user_msg:
            # Simulate the fix
            resp = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "I'll add a ValueError guard.",
                            "tool_calls": [],
                        }
                    }
                ]
            }
        else:
            resp = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": f"Acknowledged: {user_msg[:200]}",
                            "tool_calls": [],
                        }
                    }
                ]
            }

        data = json.dumps(resp).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        # Health check
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_error(404)


def main() -> int:
    port = 8080
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"fake model server listening on http://127.0.0.1:{port}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
