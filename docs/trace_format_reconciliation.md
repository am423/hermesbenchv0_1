# Trace format reconciliation (Q52)

> Phase 0 step 0: dump one existing session from `state.db` to JSONL,
> diff against the §3 "Trace format" sketch in `project.md`, and
> reconcile any mismatches. Committed before any code is written.

## Source session

- **Session ID:** `20260505_085733_b19be7`
- **Tool-call messages:** 782
- **Source DB:** `~/.hermes/state.db` (18541 messages total)
- **Dump file:** `/tmp/state_session_dump.jsonl` (1.3 MB)

## Reconciled wire format (the truth)

The §3 sketch in `project.md` was a plausible approximation.
The actual `state.db` schema is more nuanced. Here is the
**reconciled** wire format that hermesbench's `print_jsonl`
mode will emit:

### System message
```json
{"role": "system", "content": "...", "ts": <float>}
```

### User message
```json
{"role": "user", "content": "Fix the off-by-one in src/calc.py", "ts": <float>}
```

### Assistant message (with tool calls)
```json
{
  "role": "assistant",
  "content": "",                          // empty when only tool calls
  "tool_calls": [
    {
      "id": "call_YFPbnK4Y8vPsetwMEl4q4XyL",          // 22-char base62, OpenAI-style
      "type": "function",
      "function": {
        "name": "skill_view",
        "arguments": "{\"name\":\"plan\"}"               // JSON string-in-string
      }
    }
  ],
  "reasoning_content": "**Planning skills and projects**\n...",   // optional
  "ts": <float>
}
```

**Reconciliations vs the sketch:**
1. `tool_call.id` is `call_<22-char-base62>`, not `call_1` (sketch was wrong)
2. `function.arguments` is a **JSON-encoded string**, not a parsed object
3. `reasoning_content` is a **string** (markdown-formatted), not a structured field
4. `content` is empty string `""` when the assistant only emits tool calls
5. Codex-style `call_id` and `response_item_id` may also be present (not
   used by hermesbench but preserved for replay)

### Tool result message
```json
{
  "role": "tool",
  "tool_call_id": "call_YFPbnK4Y8vPsetwMEl4q4XyL",
  "content": "[skill_view] name=plan (2,865 chars)\n<the actual skill body...>"
}
```

**Reconciliations vs the sketch:**
1. `name` field is **not present** on the row (verified across 361 tool
   rows — all have `tool_name=NULL`). The tool name is reconstructed
   from the bracketed prefix `[skill_view]` at the start of `content`.
2. `content` is **not** JSON-encoded for many tools — it's a
   human-readable string with a `[<tool_name>]` prefix. The success/failure
   envelope is *not* universally present.
3. When the same `tool_call_id` produces the same output as a more recent
   call, the row contains literal text `[Duplicate tool output — same
   content as a more recent call]` instead of the real result.

### Assistant message (text only, no tool calls)
```json
{"role": "assistant", "content": "Done. The bug was...", "ts": <float>}
```

## Implications for hermesbench

1. **The §3 trace format sketch in `project.md` is now superseded**
   by this document. The Q75 `print_jsonl_plugin.py` should emit
   records matching the *reconciled* format above, not the sketch.

2. **Token IDs are not in `state.db`.** The `print_jsonl_plugin.py`
   must hook the hermes message stream *before* it lands in
   `state.db` (i.e. at the in-process emission point) to capture
   `prompt_token_ids` and `completion_token_ids`. Otherwise the
   SFT loss masks (Q45) cannot be built.

3. **Tool name recovery.** The trace jsonl should *reconstruct* the
   `name` field on tool rows by parsing the `[<tool_name>]` prefix
   in `content`. The runner is responsible for this normalization.

4. **Duplicate output collapsing.** When the source hermes has
   collapsed identical tool outputs, the trace should still
   preserve the original `content` (do not collapse further) so
   that SFT data is faithful to what the model saw.

5. **Reasoning content.** Always emitted as a separate top-level
   field, never embedded in `content`. `export-sft --include-reasoning`
   is the default (Q46).

## Verified by

```bash
sqlite3 ~/.hermes/state.db "SELECT COUNT(*) FROM messages WHERE role='tool' AND tool_name IS NOT NULL"
# Result: 0 — confirms tool rows have NULL name
```

```bash
sqlite3 ~/.hermes/state.db "SELECT tool_calls FROM messages WHERE id=13376" | head -c 300
# Confirms: id is "call_<22-char-base62>", arguments is JSON string
```

```bash
sqlite3 ~/.hermes/state.db "SELECT COUNT(*) FROM messages WHERE reasoning_content IS NOT NULL"
# Result: many — confirms reasoning is widely used by current models
```
