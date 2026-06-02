# hermesbenchv0.1 — Plan

A simple, reproducible benchmark for evaluating local models running inside the
**Hermes Agent** harness. Captures full traces (every tool call + tool result)
so the same dataset doubles as supervised fine-tuning (SFT) training data.

> Repo: `github.com/am423/hermesbenchv0_1` (private)
> Folder: `~/projects/hermesbenchv0_1/`
> v0.1 = first usable release. v0.2+ will add multi-modal, longer-horizon, and
> adversarial tool-failure scenarios.

---

## 1. Why this exists

Generic agent benchmarks (SWE-bench, AgentBench, ToolBench, τ-bench) test
broad reasoning, but **none of them are calibrated against the actual tool
surface, argument shapes, and failure envelopes a model sees inside
`run_agent.AIAgent`**. We want:

1. A score that predicts how a model will perform **in our harness, on our
   tool set, with our JSON error envelopes** — not on someone else's.
2. A captured trace for every run, in the exact message format the harness
   produces (`role: system|user|assistant|tool`, `tool_calls` JSON, `tool_call_id`
   pairing, `success: bool` results), suitable for SFT without reformatting.
3. Tasks that fit on a single local box (no Docker orchestration, no live
   internet required, no API keys) so they run on the same Arc B70 / RTX 3090
   hardware we already benchmark LLMs on.

### Data grounding

Pulled from `~/.hermes/state.db` (327 sessions, 18,541 messages, 9,224
assistant-issued tool invocations). Tool distribution:

| Tool | Count | Share | Why it's in the benchmark |
|---|---:|---:|---|
| `terminal` | 4,763 | 51.6% | Core: build, run, test, inspect |
| `read_file` | 1,167 | 12.6% | Paginated source-code reading |
| `patch` | 932 | 10.1% | Surgical code edits w/ fuzzy match |
| `search_files` | 515 | 5.6% | `rg`-backed content & file search |
| `write_file` | 446 | 4.8% | New file creation |
| `process` | 294 | 3.2% | Long-running bg process mgmt |
| `todo` | 268 | 2.9% | Multi-step planning |
| `skill_view` | 263 | 2.9% | Skill lookup |
| `execute_code` | 184 | 2.0% | Python REPL via kernel |
| `web_search` | 125 | 1.4% | Grounded lookups |
| `web_extract` | 72 | 0.8% | URL → markdown |
| `vision_analyze` | 36 | 0.4% | Image Q&A |
| `delegate_task` | 36 | 0.4% | Subagent fan-out |
| `memory` | 22 | 0.2% | Persistent facts |
| `clarify` | 20 | 0.2% | Asking the user |
| `browser_*` | 38 | 0.4% | Browser automation |
| _other_ | 89 | 1.0% | `skills_list`, `cronjob`, etc. |

**Top 6 = 88% of traffic.** Top 10 = 96%. v0.1 covers the top 6 + 4
"common but different" tools (todo, execute_code, web_search, memory) for a
10-tool surface. v0.2+ layers in browser/vision/delegate/skill_view.

Median session = 34 tool-call turns. p90 = 186. v0.1 tasks are sized 5-30
turns so they finish in 2-15 min on a 7B model.

---

## 2. Design principles

| Principle | Decision |
|---|---|
| **Simple** | Single Python entry point, no Docker, no orchestrator. Stdlib + `pyyaml` only. |
| **Reproducible** | Tasks ship a deterministic input fixture (committed to repo). Same input → same expected output. Network-disabled by default. |
| **Hermes-shaped** | Tasks are run via the real `AIAgent`, spawned as a subprocess, with `TERMINAL_ENV=tmux_isolated` so the model sees real tool schemas, real error envelopes, real conversation flow. No in-process wrapping. |
| **Isolated** | Each task gets a fresh `tmux` session, a fresh worktree, and an isolated `$HOME`. Network is `unshare --net` by default. Cleanup is signal-safe. |
| **Trace-capturing** | Every run writes `traces/<model>_<task>_<timestamp>.jsonl` with one line per message in the exact format the harness produces. |
| **SFT-ready** | Each trace is a complete conversation (`system → user → assistant(tool_calls) → tool → ... → assistant(content)`). We can slice it into `(prompt, completion)` pairs directly. |
| **Scored** | Each task has a deterministic verifier. No LLM-as-judge in v0.1. |
| **Fast feedback** | Per-task wall-clock + token count printed. Per-model summary table. |

### Non-goals (v0.1)

- Multi-modal tasks (vision/browser) → v0.2
- Adversarial prompt injection → v0.3
- Long-horizon planning (100+ turns) → v0.2
- Live network calls → v0.2 (with a `network: required` flag per task)
- LLM-as-judge for free-form answers → never, by design

---

## 3. Architecture

The core design decision: **isolation lives at the environment layer, not the
harness layer.** Hermes already has a pluggable `BaseEnvironment` backend
(local, docker, ssh, modal, daytona, singularity) selected by the
`TERMINAL_ENV` env var. Rather than wrap or replace `AIAgent`, we add a
**new backend: `tmux_isolated`**. Each benchmark task spins up a fresh
tmux session inside a fresh worktree, and the model runs against the real
`AIAgent` exactly as it would in production — same tool schemas, same error
envelopes, same conversation loop. The only thing different is the box
underneath.

### Why tmux (not docker, not a wrapper)

- **Hermes already has docker isolation** — but a Docker container breaks
  our ability to test model behavior in the *same environment* a user runs
  (no shared GPU, no shared `~/.cache/huggingface`, no shared tool
  installations, no realistic filesystem latency). The benchmark would
  measure "model on a cold box" not "model in our user's world."
- **tmux gives us isolation without virtualization.** Each task gets:
  - a fresh `tmux` session (`hermesbench-<task_id>-<uuid>`)
  - a fresh working directory (git worktree or tmp dir) that the model
    can freely `rm -rf` without nuking anything real
  - a fresh `$HOME` redirect (so `~/.bash_history`, `memory` tool
    state, and shell config are clean)
  - network-isolated mode optional (`unshare --net` if the task needs it)
  - guaranteed cleanup on exit (signal-safe tmux kill)
- **It's a thin backend**, ~150 LOC following the existing `LocalEnvironment`
  pattern, so the `BaseEnvironment` ABC gives us CWD tracking, session
  snapshot, and timeout enforcement for free.
- **The model doesn't know it's isolated.** It still calls `terminal`,
  `read_file`, `write_file`, `patch` — the only difference is that
  `terminal` is now backed by `tmux send-keys` + `tmux capture-pane` in a
  fresh session. This is exactly how a user running hermes-agent in a
  detached tmux session would experience it.

### Layout

```
hermesbenchv0_1/
├── project.md                  # this file
├── README.md                   # quick-start
├── pyproject.toml              # hermesbench package
├── hermesbench/
│   ├── __init__.py
│   ├── __main__.py             # `python -m hermesbench ...`
│   ├── cli.py                  # CLI: run / score / export / list
│   ├── runner.py               # task lifecycle: setup → spawn hermes → trace → teardown
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── tmux_isolated.py    # BaseEnvironment subclass (see §3.1)
│   │   └── worktree.py         # per-task worktree / tmp / home setup
│   ├── hermes_invocation.py    # spawns `python -m hermes_agent --quiet` per task
│   ├── scoring.py              # deterministic verifiers + metric aggregation
│   ├── trace.py                # jsonl trace recorder
│   └── tasks/
│       ├── __init__.py         # task registry
│       ├── _schema.py          # TaskSpec dataclass + validator
│       ├── t01_terminal_smoke/ # 5 tasks
│       ├── t02_file_read/      # 5 tasks
│       ├── t03_patch_edit/     # 5 tasks
│       ├── t04_search_grep/    # 5 tasks
│       ├── t05_write_new/      # 5 tasks
│       ├── t06_process_mgmt/   # 3 tasks
│       ├── t07_todo_plan/      # 3 tasks
│       ├── t08_execute_code/   # 3 tasks
│       ├── t09_web_lookup/     # 3 tasks (offline-mock fixture)
│       └── t10_memory_facts/   # 3 tasks
├── fixtures/                   # committed task input data
│   ├── small_repo/            # ~50 file Python project
│   ├── broken_code/           # 10 small broken snippets to fix
│   ├── data_files/            # CSV/JSON for search tasks
│   └── web_corpus/            # 50 mock pages for web_extract (no live net)
├── hermes_agent_patch/         # minimal upstream patch needed in hermes-agent
│   ├── TERMINAL_ENV_tmux.md    # docs: how to register the new backend
│   └── _create_environment.py  # diff: add 'tmux_isolated' to factory
├── traces/                     # gitignored: per-run output
│   └── .gitkeep
├── results/                    # gitignored: aggregated scores
│   └── .gitkeep
└── .gitignore
```

### 3.1 The `TmuxIsolatedEnvironment` backend

Subclass of `BaseEnvironment` in
`hermesbench/backend/tmux_isolated.py`. ~150 LOC. Mirrors `LocalEnvironment`
but:

```python
class TmuxIsolatedEnvironment(BaseEnvironment):
    def __init__(self, *, session_name: str, worktree: Path, isolated_home: Path,
                 network: bool = True, timeout: int = 120, **kwargs):
        super().__init__(cwd=str(worktree), timeout=timeout, **kwargs)
        self._session = session_name
        self._worktree = worktree
        self._isolated_home = isolated_home
        self._network = network
        # Created in init_session(); killed in cleanup().

    def init_session(self):
        # 1. `tmux new-session -d -s $self._session -c $self._worktree`
        # 2. `tmux send-keys -t $self._session 'export HOME=...; export PS1=; stty -echo' Enter`
        # 3. capture snapshot as in LocalEnvironment.init_session()
        super().init_session()  # writes /tmp/hermes-snap-*.sh inside the session

    def _run_bash(self, cmd_string, *, login=False, timeout=120, stdin_data=None):
        # If network=False: wrap with `unshare --net` inside the tmux send-keys
        # path. Otherwise plain bash -c as LocalEnvironment does.
        # Returns a _ThreadedProcessHandle that wraps tmux capture-pane polling.
        ...

    def cleanup(self):
        # signal-safe: `tmux kill-session -t $self._session` then
        # `rm -rf $self._worktree $self._isolated_home`
        # Idempotent: safe to call from a SIGTERM handler.
        ...
```

Key properties:
- **One tmux session per task** — not per tool call. This matches what a
  user actually does (`tmux new -s work`, run the agent, attach to watch).
- **Bash state persists across tool calls** within a task (the model can
  `cd`, `export VAR=foo`, start a long-running process and check it next
  turn). This is *crucial* — Hermes' `process` tool is built on the
  assumption of session-level persistence.
- **Worktree + isolated `$HOME` per task** — model can `rm -rf` the
  worktree, write to `~/.config/whatever`, run `git push` — none of it
  leaks to the host.
- **Optional `--net` isolation** — for tasks that should be hermetic (most
  file/code tasks), the tmux session can run under `unshare --net` so the
  model literally cannot reach the internet. Web-lookup tasks explicitly
  opt out.
- **Snapshot file lives inside the worktree** (`$worktree/.hermes-snap.sh`),
  not `/tmp`, so the session is fully self-contained.

### 3.2 The hermes-agent invocation

The benchmark runner does **not** import `AIAgent` as a library. Instead it
**spawns hermes-agent as a subprocess per task**:

```python
# hermesbench/hermes_invocation.py (sketch)
def run_task(task: TaskSpec, model: str, base_url: str) -> Path:
    worktree = worktree_setup(task)
    session_name = f"hermesbench-{task.id}-{uuid4().hex[:8]}"
    isolated_home = mkdtemp(prefix="hermesbench-home-")

    # Start tmux session with isolated env
    env_overrides = {
        "TERMINAL_ENV": "tmux_isolated",       # our new backend
        "HERMES_TMUX_SESSION": session_name,
        "HERMES_TMUX_WORKTREE": str(worktree),
        "HERMES_TMUX_HOME": str(isolated_home),
        "HERMES_TMUX_NET": "off" if task.isolated_network else "on",
        "OPENAI_BASE_URL": base_url,
        "OPENAI_MODEL": model,
        "HERMES_QUIET": "1",                   # no TUI noise
        "HERMES_SAVE_TRAJECTORY": "1",         # so hermes writes its own session
        "HERMES_TRAJECTORY_PATH": str(worktree / ".hermes-traj.jsonl"),
    }

    # Spawn hermes-agent in a way that streams all messages to our trace
    proc = subprocess.Popen(
        ["python", "-m", "hermes_agent", "--print-mode", "jsonl", "--no-tui"],
        cwd=worktree, env={**os.environ, **env_overrides},
        stdout=PIPE, stderr=PIPE, text=True,
    )
    # Feed the task prompt via stdin (hermes reads it on first turn)
    proc.stdin.write(task.prompt + "\n")
    proc.stdin.flush()

    # Stream every line of hermes's jsonl output into our trace file
    trace_path = worktree / f"trace-{task.id}.jsonl"
    with trace_path.open("w") as f:
        for line in proc.stdout:
            f.write(line)
    proc.wait(timeout=task.timeout_seconds)
    return trace_path
```

The `--print-mode jsonl` flag is the only upstream change we ask for in
`hermes-agent`: it makes hermes print every message it sends/receives
(system, user, assistant, tool) as a jsonl line on stdout. We capture
that stream as the trace. **This is the minimal invasive change** —
everything else (tool schemas, error envelopes, conversation flow) is
hermes's existing behavior.

If `--print-mode jsonl` doesn't exist upstream yet, our fallback is to
write a small hermes-agent plugin (`hermes_observability/print_jsonl.py`)
that hooks the message stream and prints to stdout. Even less invasive.

### 3.3 Why this is better than a wrapper

| Approach | Faithful to hermes? | Easy to maintain? | Trivial cleanup? | Captures real traces? |
|---|:---:|:---:|:---:|:---:|
| Subprocess hermes + tmux backend | ✓ exact | ✓ hermes stays unchanged | ✓ SIGTERM → kill tmux → rm worktree | ✓ real conversation |
| In-process `AIAgent` wrapper | ⚠ re-entrancy bugs in plugins | ✗ every hermes API change breaks us | ✗ exceptions can leak host state | ✓ real conversation |
| Custom slim harness (Mode B) | ✗ missing skills, memory, hooks | ✓ | ✓ | ✗ not real hermes |
| Docker per task | ✗ no shared GPU/cache | ✗ docker-in-docker on CI | ⚠ `docker rm -f` can hang | ✓ real conversation |

**Mode B (slim harness) is still kept** for hermes-less CI smoke tests
(e.g. `pytest tests/test_verifiers.py` doesn't need hermes-agent
installed). But the **canonical benchmark runs in subprocess mode** with
the tmux backend.

Mode selection:
- `python -m hermesbench run --task ...` → subprocess + tmux (default)
- `python -m hermesbench run --task ... --slim` → in-process slim harness
  (for hermes-less CI; flagged in results so it's never compared head-to-head)

### Trace format (one jsonl line per harness message)

```json
{"role": "system", "content": "...", "ts": 1700000000.0}
{"role": "user", "content": "Fix the off-by-one in src/calc.py", "ts": ...}
{"role": "assistant", "content": null, "tool_calls": [
  {"id": "call_1", "type": "function",
   "function": {"name": "read_file",
                "arguments": "{\"path\": \"src/calc.py\"}"}}], "ts": ...}
{"role": "tool", "tool_call_id": "call_1",
 "name": "read_file",
 "content": "{\"success\": true, \"content\": \"...\"}", "ts": ...}
{"role": "assistant", "content": "Done. The bug was...", "ts": ...}
```

This is the **exact wire format** `AIAgent.run_conversation()` produces, so
traces are SFT-ready with zero transformation.

---

## 4. Task taxonomy (40 tasks in v0.1)

Each task is a directory with:
- `task.yaml` — name, prompt, allowed_tools, max_turns, expected_artifacts
- `verifier.py` — deterministic Python function returning `(passed: bool, details: dict)`
- `fixture/` — committed input data (gitignored size caps apply)

### Category 1: `terminal` (5 tasks)

| ID | Task | Tests |
|---|---|---|
| `t01_terminal_smoke` | Run a build, capture exit code | `terminal` JSON args, non-zero exit handling |
| `t02_terminal_compile` | Compile a C file with intentional warnings | Long output truncation, error extraction |
| `t03_terminal_pipeline` | Pipe `cat \| grep \| wc` | Multi-command chaining |
| `t04_terminal_env` | Check an env var that does/doesn't exist | Reading error messages |
| `t05_terminal_long` | Start a 5-second sleep, observe via `process` list, kill it | `terminal` + `process` handoff |

### Category 2: `read_file` (5 tasks)

| ID | Task | Tests |
|---|---|---|
| `t01_read_head` | Read first 50 lines | offset/limit args |
| `t02_read_tail` | Read last 20 lines | Offset calculation |
| `t03_read_paginated` | Read 500-line file in 3 chunks | Multi-call pagination |
| `t04_read_missing` | Read non-existent file | Error envelope recovery |
| `t05_read_nested` | Read deeply-nested path | Path quoting |

### Category 3: `patch` (5 tasks) — *the hardest, most failure-prone tool*

| ID | Task | Tests |
|---|---|---|
| `t01_patch_unique` | Replace a unique function | Successful patch |
| `t02_patch_ambiguous` | Match appears twice, must disambiguate via context | Reading "Did you mean" hints |
| `t03_patch_unicode` | Replace string with non-ASCII | Encoding handling |
| `t04_patch_multiline` | 30-line block replace | Large old_string |
| `t05_patch_v4a` | Use `mode=patch` with V4A format | Knowing the V4A syntax |

### Category 4: `search_files` (5 tasks)

| ID | Task | Tests |
|---|---|---|
| `t01_search_basic` | Find all files containing "TODO" | `pattern` + `path` |
| `t02_search_with_glob` | Search only `*.py` | `file_glob` arg |
| `t03_search_output` | Switch `output_mode: files_only \| content \| count` | Mode selection |
| `t04_search_regex` | Use a regex pattern | Regex escaping |
| `t05_search_no_match` | Handle empty result | No false positives |

### Category 5: `write_file` (5 tasks)

| ID | Task | Tests |
|---|---|---|
| `t01_write_new` | Create a new file | Basic write |
| `t02_write_overwrite` | Overwrite existing file | No diff-merge failure |
| `t03_write_large` | Write a 10K-line file | Token-efficient content |
| `t04_write_with_unicode` | Write file with non-ASCII content | Encoding |
| `t05_write_path_create` | Write to a path whose parent dirs don't exist | Error recovery |

### Category 6: `process` (3 tasks)

| ID | Task | Tests |
|---|---|---|
| `t01_process_list` | List bg processes | `process(action="list")` |
| `t02_process_kill` | Kill a leaked process | `process(action="kill")` |
| `t03_process_poll` | Poll a running process for output | `process(action="poll")` |

### Category 7: `todo` (3 tasks)

| ID | Task | Tests |
|---|---|---|
| `t01_todo_plan` | Decompose a 4-step task into todos | Multi-item todos array |
| `t02_todo_update` | Mark item in_progress, then completed | Status transitions |
| `t03_todo_replan` | Insert a new todo mid-flight | `merge: true` semantics |

### Category 8: `execute_code` (3 tasks)

| ID | Task | Tests |
|---|---|---|
| `t01_repl_math` | Compute a non-trivial result in Python | REPL state persistence |
| `t02_repl_pandas` | Load a CSV, aggregate, return answer | Pandas correctness |
| `t03_repl_debug` | Find a bug by running code incrementally | Multi-step REPL |

### Category 9: `web_search` / `web_extract` (3 tasks — **offline-mocked**)

| ID | Task | Tests |
|---|---|---|
| `t01_web_search` | Search for a fact | Query formulation |
| `t02_web_extract` | Extract content from a known URL | URL list construction |
| `t03_web_no_result` | Handle empty search | No hallucination |

These use a local mock server (`fixtures/web_corpus/`) — no live internet.

### Category 10: `memory` (3 tasks)

| ID | Task | Tests |
|---|---|---|
| `t01_memory_save` | Save a fact | `memory(action="add")` |
| `t02_memory_recall` | Recall across turns | Persistence check |
| `t03_memory_avoid_dup` | Don't re-save a known fact | Dedup judgement |

---

## 5. Scoring

Per-task score = `verifier.py` returns `passed: bool`. Aggregate:

- **Pass rate** = tasks passed / tasks attempted (primary metric)
- **Tool-use efficiency** = median tool calls per task (lower = better, with floor)
- **Token efficiency** = input+output tokens / task
- **Wall-clock** = seconds / task
- **Recovery rate** = % of `success: false` tool results followed by a correct
  next move within 2 turns (measures error-recovery skill)
- **Format compliance** = % of tool calls with valid JSON `arguments` matching
  the schema (no extra/missing keys, right types)

A single model produces a results row like:

```
model: qwen2.5-coder-7b-instruct-q4_k_m
pass_rate:        28/40 (70.0%)
tool_efficiency:  median 6.1 calls/task
token_efficiency:  14,200 tok/task avg
wall_clock:       38.4 s/task avg
recovery_rate:    81.2%
format_compliance: 99.4%
```

### Verifier pattern

```python
# hermesbench/tasks/t03_patch_edit/t02_patch_ambiguous/verifier.py
def verify(workdir: Path, trace: list[dict]) -> tuple[bool, dict]:
    target = workdir / "src" / "config.py"
    if not target.exists():
        return False, {"reason": "file missing"}
    content = target.read_text()
    # Expect: only ONE block of `TIMEOUT = 30` (the duplicated one was fixed)
    count = content.count("TIMEOUT = 30")
    if count != 1:
        return False, {"reason": f"expected 1 'TIMEOUT=30', got {count}"}
    return True, {"checks": {"timeout_count": count}}
```

---

## 6. CLI

```bash
# List tasks
python -m hermesbench list
python -m hermesbench list --category patch

# Run a single task against a model
python -m hermesbench run \
    --model qwen2.5-coder-7b-instruct-q4_k_m \
    --task t03_patch_edit/t02_patch_ambiguous \
    --base-url http://127.0.0.1:8080/v1

# Run a full category
python -m hermesbench run --model ... --category patch

# Run the full 40-task suite
python -m hermesbench run --model ... --all

# Re-score from existing traces (no re-run)
python -m hermesbench score traces/qwen*.jsonl

# Export traces as SFT jsonl (one completion per line)
python -m hermesbench export-sft \
    --in traces/ \
    --out sft_dataset.jsonl \
    --format openai
```

---

## 7. Implementation phases

### Phase 1 — Skeleton + `TmuxIsolatedEnvironment` backend (Day 1-3)
- [ ] `pyproject.toml` + `hermesbench/` package skeleton
- [ ] `backend/tmux_isolated.py` — first cut: `init_session`, `_run_bash`, `cleanup`
- [ ] `backend/worktree.py` — `worktree_setup(task)` copies fixtures, sets up isolated `$HOME`
- [ ] `runner.py` — task lifecycle: setup → spawn hermes → trace → teardown
- [ ] Manual smoke test: 1 task against a real model, confirm tmux session is
      created, model runs, tmux is killed, worktree is removed
- [ ] Add the `TERMINAL_ENV=tmux_isolated` branch to hermes-agent's
      `_create_environment()` factory (1-line PR to `tools/terminal_tool.py`)

### Phase 2 — `hermes_invocation.py` + jsonl trace streaming (Day 4-5)
- [ ] Spawn `python -m hermes_agent --print-mode jsonl --no-tui` as a subprocess
- [ ] Stream every jsonl line from hermes's stdout into the trace file
- [ ] If `--print-mode jsonl` doesn't exist upstream, build the
      `hermes_observability/print_jsonl.py` plugin as a fallback
- [ ] Verify trace format matches the wire format in §3 "Trace format"

### Phase 3 — Author 40 tasks (Day 6-10)
- [ ] Categories 1-6 (29 tasks): file/terminal/process — the 88% bulk
- [ ] Categories 7-10 (11 tasks): todo/exec_code/web/memory
- [ ] Each task gets: `task.yaml`, `verifier.py`, fixture data
- [ ] Each task declares `isolated_network: bool` in `task.yaml`
      (defaults to `false` for hermeticity)
- [ ] Commit fixtures to repo (size cap: 100 KB per fixture, gzip if larger)

### Phase 4 — Mode B (slim harness) for hermes-less CI (Day 11)
- [ ] `HermesBenchHarness` 200-line implementation
- [ ] Auto-fallback test: hermes-less env, confirm Mode B runs
- [ ] Results from Mode B runs are tagged `mode=slim` so they're never
      compared head-to-head with subprocess mode

### Phase 5 — Scoring + reporting (Day 12)
- [ ] `scoring.py` computes all 6 metrics
- [ ] `results/<model>_<date>.json` per-run aggregate
- [ ] Pretty-print summary table

### Phase 6 — Export to SFT format (Day 13)
- [ ] `export-sft` command: traces → OpenAI / ShareGPT / Hermes message formats
- [ ] Sanity check: load exported SFT jsonl, count completions, inspect a sample

### Phase 7 — Initial baseline runs (Day 14-15)
- [ ] Run against 3 representative local models: a small (3-4B), a medium (7-8B), a large (32-70B)
- [ ] Publish `results/baseline_<date>.md` in the repo
- [ ] Commit traces (or a sample of them) so others can reproduce
- [ ] Confirm: every task's tmux session was killed, every worktree was rm-rf'd
      (post-mortem script scans `/tmp` and `tmux ls` for leaks)

### Phase 8 — v0.1 release tag (Day 16)
- [ ] README with quick-start, results table, "how to add a task" guide,
      "how to add a new environment backend" guide
- [ ] Open upstream PR to hermes-agent: register `tmux_isolated` backend
- [ ] `git tag v0.1`
- [ ] Internal dogfood: run the suite in our own dev loop for 1 week,
      fix anything that breaks

---

## 8. v0.2+ roadmap (out of scope for v0.1, listed for context)

- **v0.2 — Multi-modal + longer horizon:** vision tasks (image Q&A), browser tasks (offline mock DOM), 60-100 turn projects
- **v0.3 — Adversarial:** prompt-injection resistance, ambiguous user prompts, broken-tool recovery
- **v0.4 — Live net:** opt-in `network: required` flag, real `web_search`/`web_extract`
- **v0.5 — Cross-session:** tasks that span multiple `AIAgent` sessions with persistent memory
- **v0.6 — Skill usage:** force-load a skill, test if model invokes `skill_view` to read it
- **v1.0 — Public leaderboard:** website hosting results, model submission PR workflow

---

## 9. Success criteria for v0.1

- [ ] All 40 tasks have a passing implementation
- [ ] `python -m hermesbench run --all` works on a fresh checkout in <30 min on a 7B model
- [ ] Three baseline models run cleanly, results published
- [ ] At least 100 trace jsonl files committed (dogfooding)
- [ ] `export-sft` produces a valid jsonl that fine-tunes a model to ≥+5% pass-rate on a held-out task
- [ ] README lets a new user run their first task in <5 min
- [ ] `TmuxIsolatedEnvironment` backend passes a leak test: after 40 task
      runs, `tmux ls` shows no `hermesbench-*` sessions and
      `/tmp/hermesbench-*` is empty
- [ ] `hermes-agent` upstream has the `TERMINAL_ENV=tmux_isolated` branch
      merged (or our patch is vendored in `hermes_agent_patch/`)
- [ ] Subprocess-mode runs use real `AIAgent`; verified by grepping
      trace jsonl for messages whose `role=tool` carries
      `success: bool` envelopes (a sign the real tool handlers ran)

---

## 10. Open questions

1. **Hermes subprocess vs in-process?** Subprocess is more faithful but
   slower (Python startup × 40 tasks ≈ +60s). **Decision: subprocess +
   tmux backend, always. Speed is not the bottleneck.**
2. **Mode A vs Mode B in CI?** Mode A drags in all of hermes-agent's
   deps. If we want a slim CI image, Mode B is the path. **Decision: ship
   both, default to subprocess Mode A, tag results with mode so they
   can't be confused.**
3. **What fixture size cap?** 100 KB / task keeps the repo under 5 MB.
   **Decision: 100 KB; document the cap in `tasks/_schema.py`.**
4. **Token-budget per task?** Unbounded makes 70B models OOM.
   **Decision: 8K context hard cap per task, configurable up to 32K.
   Refused if exceeded.**
5. **Should verifiers be allowed to import hermes-agent?** No — verifiers
   must be stdlib-only so they're portable. **Decision: enforce via lint.**
6. **Live web tasks in v0.1?** No — adds flakiness. **Decision: mock
   corpus for v0.1, opt-in live in v0.4. Tasks opt into network via
   `isolated_network: true` in `task.yaml`.**
7. **Should the tmux session be persistent across turns or per-call?**
   Persistent — the model's `process` tool assumes long-running bg
   processes can be polled across turns. **Decision: one tmux session
   per task, killed in `cleanup()`.**
8. **`unshare --net` or full network namespace?** `--net` only is enough
   for our hermeticity goal (block internet, keep loopback for
   localhost). **Decision: `unshare --net` per session when
   `isolated_network: false`.**
9. **What if hermes-agent doesn't have `--print-mode jsonl` yet?**
   Fallback: ship a 50-LOC `print_jsonl` plugin that hooks the message
   stream. **Decision: try CLI flag first, fall back to plugin. Both
   paths land in v0.1.**

---

## 11. References

- Hermes Agent harness: `~/.hermes/hermes-agent/run_agent.py` (AIAgent)
- Tool schemas: `~/.hermes/hermes-agent/tools/registry.py` + `toolsets.py`
- Environment backend ABC: `~/.hermes/hermes-agent/tools/environments/base.py`
- Existing backends: `local.py`, `docker.py`, `ssh.py`, `modal.py`,
  `daytona.py`, `singularity.py` (use `LocalEnvironment` as the
  structural reference for `TmuxIsolatedEnvironment`)
- Backend selection: `TERMINAL_ENV` env var, dispatched by
  `_create_environment()` in `tools/terminal_tool.py:1143`
- Session data source: `~/.hermes/state.db` (SQLite, FTS5-indexed)
- AIAgent loop contract: see `AGENTS.md` § "Agent Loop"
