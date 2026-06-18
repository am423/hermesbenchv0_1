# Plan Review: PLAN_ANALYSIS.md — Rubric Grade

## GRADE: 52/100

---

## RUBRIC

| Dimension | Score | Max | Notes |
|-----------|-------|-----|-------|
| Root Cause Accuracy | 18 | 20 | 4 problems identified correctly, 1 minor error |
| Data Analysis Quality | 8 | 15 | Good survey but missing critical structural details |
| Fix Correctness | 5 | 20 | Two critical code errors, missing normalization step |
| Training Data Design | 6 | 15 | Format partially wrong, missing key details |
| Verifier Upgrade Design | 4 | 10 | Vague, doesn't address actual verifier code |
| Task Upgrade Design | 4 | 10 | Vague "new tasks from real sessions" with no specifics |
| Completeness | 3 | 5 | Missing error handling, dedup, context window management |
| Execution Plan | 4 | 5 | Reasonable phases but missing integration tests |
| **TOTAL** | **52** | **100** | |

---

## GAPS (10 found)

### CRITICAL (blocks execution)

**G1: Session export is ONE JSON blob, not per-message JSONL**
- Location: Plan §"Session export format", line 110-124
- Problem: Plan says session export produces JSONL with one message per line. Reality: `hermes sessions export` produces a file with ONE line — the entire session as a single JSON object with a `messages` array inside it. The existing `read_trace()` function in trace.py reads line-by-line expecting `{"role": "...", "content": "..."}` per line. It will parse the single export line as one message with `role: null`, `content: null` and fail.
- Fix: Add a conversion step that extracts `data["messages"]` from the export blob and writes each message as a separate JSONL line to trace.jsonl.

**G2: Plan doesn't address trace.py normalization**
- Location: Plan Phase 1.2, line 137-140
- Problem: Plan says "Parse exported JSONL into verifier-compatible format" but doesn't specify how. The existing `read_trace()` in trace.py has a `_normalize()` function that reconstructs tool names from `[name]` prefixes in tool content. The session export format has tool content as JSON strings like `{"output": "hello", "exit_code": 0}` — NOT prefixed with `[terminal]`. So the normalizer won't reconstruct the tool name.
- Fix: When converting export to trace JSONL, add `[terminal]` prefix to tool message content, or update `_normalize()` to handle JSON tool content.

**G3: spawn_hermes uses `hermes -z` but plan says use `hermes chat -q` — code not shown**
- Location: Plan Phase 1.1, line 132-135
- Problem: Plan says "Use `hermes chat -q` instead of `hermes -z`" but doesn't show the actual code change. The current spawn_hermes code builds the command as `[hermes_bin, "-z", task_prompt, ...]`. The fix needs to change to `[hermes_bin, "chat", "-q", task_prompt, ...]` AND change `shutil.which("hermes")` for the binary path AND remove `-z` flag entirely. Without showing the exact diff, the implementer may miss one of these three changes.
- Fix: Show the exact before/after for the cmd list construction.

**G4: Session ID capture from stderr is unreliable**
- Location: Plan Phase 1.1, line 135
- Problem: Plan says "Capture session_id from stderr output". The session_id line (`session_id: 20260617_194821_30e302`) appears on stderr AFTER the agent completes. But `hermes chat -q` with `-Q` (quiet) mode outputs the session_id to stderr. However, the timing is not guaranteed — the subprocess might not have flushed stderr before `proc.wait()` returns. Also, the `-Q` flag suppresses some stderr output, so the session_id format might vary.
- Fix: Read stderr fully after `proc.wait()`, parse with regex `session_id:\s*(\S+)`. Add fallback: if no session_id, write stdout as plain text trace.

### HIGH (significant quality impact)

**G5: Unsloth/ShareGPT format doesn't support tool_calls natively**
- Location: Plan Phase 3.2, line 170-182
- Problem: Plan shows `{"from": "gpt", "value": "", "tool_calls": [...]}` in ShareGPT format. Unsloth's ShareGPT converter does NOT parse `tool_calls` — it only reads `value` as the text content. Tool call training in Unsloth requires a different approach: either (a) serialize tool calls into the text content as XML/JSON strings, or (b) use the OpenAI messages format directly with a custom collator.
- Fix: Use OpenAI `messages` format (not ShareGPT `conversations`). Include tool_calls as structured fields. For Unsloth, use `UnslothFlexGen` or custom chat template that renders tool calls as text the model can learn.

**G6: No context window management for training data**
- Location: Plan Phase 3.3, line 184-188
- Problem: "Maximum 100 messages" is arbitrary. Some sessions have 1000+ messages (792, 834, 863, 922, 988, 1024, 1032 messages). Even 100 messages with full tool output can exceed 32K tokens. The plan doesn't address truncation strategy.
- Fix: Token-budget-based filtering (e.g., max 4096 tokens per example). For long sessions, extract the most relevant segment (the tool call + result + response). Sliding window for multi-turn examples.

**G7: Tool content in session export is JSON, verifiers expect `[name]` prefix**
- Location: Plan doesn't address this
- Problem: Session export tool messages have content like `{"output": "hello-hermesbench", "exit_code": 0}`. The existing `trace.py` normalizer expects `[terminal] hello-hermesbench` format to reconstruct tool names. Without this, verifiers that check tool results by name won't work.
- Fix: In the export-to-trace conversion, prefix tool content with `[tool_name]` to match existing normalizer expectations. OR update verifiers to parse JSON tool content.

### MEDIUM (completeness)

**G8: Deduplication strategy is vague**
- Location: Plan Phase 3.3, line 188
- Problem: "Deduplicate by tool call pattern similarity" — no algorithm specified. With 627 sessions, many will have identical tool call sequences (e.g., the cron jobs that run daily).
- Fix: Hash the first N tool call names + arguments. Dedupe by hash. Keep the shortest/best example per hash.

**G9: New tasks (t12_real_world) have no concrete designs**
- Location: Plan Phase 4.2, line 203-206
- Problem: "Use mined session patterns to create realistic tasks" — no specific tasks defined. No task.yaml, no verifier, no fixtures.
- Fix: Define at least 3 concrete task specs from real session data (e.g., "read a file, identify the bug, patch it" based on actual sessions that did this).

**G10: Verifier upgrade is vague**
- Location: Plan Phase 4.1, line 197-201
- Problem: "Accept both JSONL trace AND worktree-state verification" — but doesn't show how to modify the existing `verify(worktree, trace)` signature or the verifier code. 11 verifiers need updating but no specific changes shown.
- Fix: Show one concrete verifier modification (e.g., t01_echo) as a template, then list the changes needed for each of the other 10.

---

## FIXES TO REACH 100/100

### G1 Fix: Export-to-trace conversion function
Add to runner.py or hermes_invocation.py:
```python
def export_to_trace(session_export_path: Path, trace_path: Path) -> bool:
    """Convert hermes session export (one JSON blob) to per-message JSONL."""
    import json
    data = json.loads(session_export_path.read_text())
    messages = data.get("messages", [])
    with trace_path.open("w") as f:
        for msg in messages:
            # Prefix tool content with [tool_name] for normalizer
            if msg.get("role") == "tool":
                content = msg.get("content", "")
                tool_calls = [m for m in messages if m.get("role") == "assistant" 
                             and any(tc.get("id") == msg.get("tool_call_id") 
                                    for tc in (m.get("tool_calls") or []))]
                if tool_calls:
                    tc = tool_calls[0]
                    for call in (tc.get("tool_calls") or []):
                        if call.get("id") == msg.get("tool_call_id"):
                            name = call.get("function", {}).get("name", "tool")
                            msg["content"] = f"[{name}] {content}"
                            break
            f.write(json.dumps(msg) + "\n")
    return True
```

### G2 Fix: Show trace.py normalization compatibility
The conversion above produces `[terminal] {"output": "hello"}` which the existing `_normalize()` will parse correctly, extracting `name = "terminal"`.

### G3 Fix: Exact spawn_hermes diff
```python
# BEFORE:
hermes_bin = str(hermes_path / "hermes")
cmd = [hermes_bin, "-z", task_prompt, "--yolo", "-Q", "-t", toolsets, "--max-turns", str(max_turns)]

# AFTER:
import shutil
hermes_bin = shutil.which("hermes") or str(hermes_path / "hermes")
cmd = [hermes_bin, "chat", "-q", task_prompt, "--yolo", "-Q", "-t", toolsets, "--max-turns", str(max_turns)]
```

### G4 Fix: Session ID capture with fallback
```python
stdout_text = proc.stdout.read() if proc.stdout else ""
stderr_text = proc.stderr.read() if proc.stderr else ""
session_id = None
for line in stderr_text.splitlines():
    m = re.search(r"session_id:\s*(\S+)", line)
    if m:
        session_id = m.group(1)
        break
# Export session to trace JSONL
if session_id:
    export_to_trace(session_id, trace_path)
else:
    # Fallback: write stdout as plain text
    trace_path.write_text(stdout_text)
```

### G5 Fix: Use OpenAI messages format, not ShareGPT
```json
{"messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "Run echo hello"},
    {"role": "assistant", "content": null, "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "terminal", "arguments": "{\"command\": \"echo hello\"}"}}]},
    {"role": "tool", "tool_call_id": "call_1", "content": "[terminal] hello"},
    {"role": "assistant", "content": "Output: hello"}
]}
```

### G6 Fix: Token budget filtering
```python
# Estimate tokens as chars/4, filter examples > 4096 tokens
MAX_TOKENS = 4096
for msg in messages:
    total_chars += len(msg.get("content", "") or "")
    total_chars += len(json.dumps(msg.get("tool_calls", [])))
if total_chars / 4 > MAX_TOKENS:
    # Extract just the key segment: user prompt + first tool call + result
    extract_segment(messages, max_tokens=MAX_TOKENS)
```

### G7 Fix: Tool content prefixing (in G1 fix code above)

### G8 Fix: Hash-based deduplication
```python
def dedup_hash(messages):
    """Hash the first 5 tool call names + first 100 chars of arguments."""
    tools = []
    for m in messages:
        for tc in (m.get("tool_calls") or []):
            name = tc.get("function", {}).get("name", "")
            args = tc.get("function", {}).get("arguments", "")[:100]
            tools.append(f"{name}:{args}")
    return hash(tuple(tools[:5]))
```

### G9 Fix: Three concrete new tasks from session data
```
t12_real_world/t01_multi_tool_workflow: 
  Prompt: "Read the file main.py, find any bugs, and fix them"
  Verify: read_file called + patch called + file modified
  
t12_real_world/t02_error_recovery:
  Prompt: "Try to read /nonexistent, then find the correct file"
  Verify: read_file on missing path attempted + second read_file on existing path
  
t12_real_world/t03_search_and_report:
  Prompt: "Find all TODO comments in this repo and list them"
  Verify: search_files called with TODO pattern + result reported
```

### G10 Fix: Concrete verifier modification
```python
# t01_echo verifier upgrade — worktree-state fallback:
def verify(worktree: Path, trace: list[dict]) -> VerifierResult:
    # Path 1: Check trace for terminal tool call (existing)
    used_terminal = any(
        (tc.get("function") or {}).get("name") == "terminal"
        for msg in trace if msg.get("role") == "assistant"
        for tc in (msg.get("tool_calls") or [])
    )
    if used_terminal:
        # Check final message has expected output
        for msg in reversed(trace):
            if msg.get("role") == "assistant" and msg.get("content"):
                if "hello-hermesbench" in msg["content"]:
                    return VerifierResult(status="PASS", reason="ok")
                break
    # Path 2: Worktree-state fallback (NEW)
    # If no trace evidence but worktree has evidence, still pass
    # (e.g., file was created with correct content)
    # For echo task there's no worktree evidence, so this N/A here
    # but for file tasks this would check file existence/content
    return VerifierResult(status="FAIL", reason="model did not use terminal tool")
```

---

## PATH TO 100

```
Current:                    52/100
G1 fix (trace conversion):  +8  → 60
G2 fix (normalizer compat): +5  → 65
G3 fix (exact spawn diff):  +5  → 70
G4 fix (session ID cap):    +4  → 74
G5 fix (OpenAI format):     +5  → 79
G6 fix (token budget):      +3  → 82
G7 fix (tool prefix):       +3  → 85
G8 fix (dedup hash):        +2  → 87
G9 fix (concrete tasks):    +5  → 92
G10 fix (verifier diff):    +4  → 96
Full integration test:      +2  → 98
Error handling throughout:  +2  → 100
```
