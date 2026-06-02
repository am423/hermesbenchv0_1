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
| **Simple** | Single Python entry point, no Docker, no orchestrator. Runtime deps: `pyyaml`, `pyte` (cast capture), `psutil` (CPU/RAM/process), `pynvml` (NVIDIA GPU), `py-cpuinfo` (CPU model). Build deps: `agg` binary (GIF), `ffmpeg` (MP4). |
| **Reproducible** | Tasks ship a deterministic input fixture (committed to repo). Same input → same expected output. Network-disabled by default. |
| **Hermes-shaped** | Tasks are run via the real `AIAgent`, spawned as a subprocess, with `TERMINAL_ENV=tmux_isolated` so the model sees real tool schemas, real error envelopes, real conversation flow. No in-process wrapping. |
| **Isolated** | Each task gets a fresh `tmux` session, a fresh worktree, and an isolated `$HOME`. Network is `unshare --net` by default. Cleanup is signal-safe. |
| **Trace-capturing** | Every run writes `traces/<model>_<task>_<timestamp>.jsonl` with one line per message in the exact format the harness produces. |
| **X-shareable** | Every task also produces a `.cast` file (asciinema v2 format) of the model's terminal session, captured via `tmux pipe-pane` from the moment the task starts to cleanup. Render to GIF/MP4 with one command. |
| **Stats-capturing** | Every task also produces a `.stats.jsonl` sibling with hardware telemetry (GPU temp/power/util, CPU temp/power/util, RAM, NVMe, host power). Sampled at 5 Hz, zero benchmark interference. Surfaced in scoring and in the `.cast` overlay. |
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
│   ├── cli.py                  # CLI: run / score / export / list / render
│   ├── runner.py               # task lifecycle: setup → spawn hermes → trace → teardown
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── tmux_isolated.py    # BaseEnvironment subclass (see §3.1)
│   │   ├── recorder.py         # pyte-based pipe-pane sink → .cast (§3.1a)
│   │   └── worktree.py         # per-task worktree / tmp / home setup
│   ├── hermes_invocation.py    # spawns `python -m hermes_agent --quiet` per task
│   ├── scoring.py              # deterministic verifiers + metric aggregation
│   ├── trace.py                # jsonl trace recorder
│   ├── statsd/                 # system statistics collector (§3.1b)
│   │   ├── __init__.py
│   │   ├── __main__.py         # `python -m hermesbench.statsd ...`
│   │   ├── collector.py        # sampling loop
│   │   ├── pinning.py          # core-pick + nice/ionice
│   │   └── sources/
│   │       ├── cpu.py
│   │       ├── gpu_nvidia.py
│   │       ├── gpu_amd.py
│   │       ├── gpu_intel.py
│   │       ├── memory.py
│   │       ├── nvme.py
│   │       ├── host_power.py
│   │       └── process.py
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
├── examples/                   # 3 reference GIFs (easy/medium/hard) + raw casts
│   └── .gitkeep
├── traces/                     # gitignored: per-run output (jsonl + cast)
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

### 3.1a Terminal capture for X sharing (always-on)

Every task records its full terminal session as an asciinema v2 `.cast`
file. This is the artifact you post to X — no extra work, no model
behavior change. Wire-up is purely at the `tmux` layer via
`pipe-pane`, so the model has zero idea it's being recorded.

**Capture mechanism — `tmux pipe-pane` to a python `pyte` screen
emulator.** Two-step:

1. **Attach a pipe** in `init_session()`:
   ```bash
   tmux pipe-pane -t $SESSION -o "python3 $HERMESBENCH/recorder.py $CAST_FILE"
   ```
2. **The recorder** is a 80-LOC Python script that uses `pyte` (a
   pure-Python VT100/xterm emulator) to maintain a screen buffer, then
   flushes diffs to the `.cast` file in asciinema v2 format on a
   100ms tick.

Why this design:
- **`pyte` is screen-accurate** — it understands ANSI escape codes, cursor
  movement, color, alternate screen buffer, `\r` progress bars, etc.
  Critical because models use progress bars (`pip install`, `cargo
  build`, `pytest -v`) all the time and we don't want the cast to
  look like garbled text.
- **Diff-based flush** is the asciinema v2 idiom — we don't dump the full
  screen every frame, we emit only what changed, so file sizes stay
  small (typical 5-minute cast ≈ 50-200 KB).
- **Always-on, zero opt-in** — every `TmuxIsolatedEnvironment.init_session()`
  pipes unconditionally. The `.cast` file is one of the canonical
  artifacts alongside the trace jsonl.

**Layout addition:**

```
hermesbench/
├── backend/
│   ├── tmux_isolated.py        # BaseEnvironment subclass
│   └── recorder.py             # pyte-based pipe-pane sink → .cast
```

**CLI to render `.cast` to shareable formats:**

```bash
# GIF (default for X, Twitter caps at 15MB; we target <8MB)
python -m hermesbench render trace.cast --format gif --out trace.gif

# MP4 (better quality, can host anywhere)
python -m hermesbench render trace.cast --format mp4 --out trace.mp4

# Trim (drop the first/last N seconds; for skipping warmup)
python -m hermesbench render trace.cast --format gif --trim-start 5s --trim-end 2s

# Speed up boring parts (e.g. apt-get install) — model finished, viewer doesn't need 30s
python -m hermesbench render trace.cast --format gif --speed 2.0

# Concat multiple tasks into one reel
python -m hermesbench render-reel traces/qwen*.cast --format gif --out reel.gif
```

**Render backend stack (no install surprises):**

| Format | Tool | Why |
|---|---|---|
| `.cast` | `pyte` + our recorder | Source of truth, replayable with `asciinema play` |
| `.gif` | `agg` (asciinema gif generator) | High-quality, palette-aware, the de-facto choice for X |
| `.mp4` | `ffmpeg` (already on system) | Universal, 1080p+ |
| `.txt` | raw terminal log (cat) | For README embedding |
| `.svg` | `termsvg` if installed | Static screenshots |

`agg` is a single Rust binary (~3 MB), pull it as a build dep or pin
version. `ffmpeg` is already installed. The `render` CLI checks
availability and degrades gracefully — if `agg` missing, fall back to
`ffmpeg` + a quick `chafa` frame rasterization (no install needed
beyond ffmpeg).

**What gets captured (and what doesn't):**

- ✅ All `terminal` tool output — this is the whole point
- ✅ All error messages, stack traces, prompts the model sees
- ✅ Model's own thinking? **No.** We capture the *terminal*, not the
  LLM's hidden chain-of-thought. Reasoning_content stays in the jsonl
  trace, not in the cast.
- ✅ TUI elements, progress bars, pagers (`less`, `vim`, `htop`) — `pyte`
  handles alternate screen buffer correctly
- ❌ TUI prompts (the hermes REPL's spinner, etc.) — they don't exist
  in `--no-tui --print-mode jsonl` mode anyway

**X-specific quality notes:**

- X video caps at 140s / 500MB. Most task casts are 30-120s. If a task
  runs longer, `render` auto-suggests `--speed 2.0` to halve length.
- X autoplay is muted — visual hooks matter. The `render` CLI has a
  `--add-caption` flag that overlays the task name + pass/fail at the
  start, e.g.:
  `t03_patch_edit / t02_patch_ambiguous — ✅ PASS — qwen2.5-coder-7b`
- Watermark? Optional `--watermark "hermesbench v0.1"` in the corner
  (per the user's YC-quality + branding bar; matches the watermark
  convention from the ascii-video skill — visible from frame 0, no
  fade-in, so loops are seamless).

**Sanity test (added to CI):**

```python
def test_recorder_roundtrip():
    """A 5-line bash session should produce a valid .cast that re-renders."""
    with tempfile.TemporaryDirectory() as d:
        cast = Path(d) / "x.cast"
        run_in_tmux("echo hello; sleep 0.2; ls; echo done", cast_path=cast)
        # Round-trip: read the cast, verify it's valid asciinema v2
        frames = list(read_cast(cast))
        assert len(frames) >= 4
        assert "hello" in screen_text(frames[-1])
        # And it renders without error
        gif = render(cast, format="gif")
        assert gif.stat().st_size > 1000
```

### 3.1b System statistics collector (always-on, zero interference)

Every task run also produces a `.stats.jsonl` sibling to the `.cast`.
This is the "is the model just slow, or is it throttling?" data — and
it's also what makes benchmark numbers defensible across runs (different
ambient temp, different cool-down time, different background load all
show up here).

**What we collect (per sample, 5 Hz default, configurable to 1-20 Hz):**

| Group | Source | Fields |
|---|---|---|
| **CPU package** | `psutil` + `/sys/class/thermal/k10temp` + `turbostat` if root | freq (MHz per core), util %, temp °C, package power W (via RAPL MSR when available, else `powertop -i` estimate) |
| **CPU per-core** | `psutil.cpu_percent(percpu=True)` | util % per logical core (so we can see if llama.cpp is using all cores or just a few) |
| **GPU (NVIDIA)** | `nvidia-smi --query-gpu=...` via `pynvml` | index, name, util.gpu %, util.mem %, temp °C, power.draw W, power.limit W, clocks.gr MHz, clocks.mem MHz, mem.used MiB, mem.total MiB, fan %, pstate, throttled reasons |
| **GPU (AMD/Intel)** | `/sys/class/drm/card*/device/hwmon/hwmon*/{temp1_input,power1_average,power1_cap,gt_cur_freq_mhz}` + `intel_gpu_top`/`radeontop` when available | temp °C, package power W, freq MHz, util % |
| **RAM** | `psutil.virtual_memory()` | used MiB, total MiB, swap used, dirty/writeback pages |
| **VRAM (per GPU)** | `pynvml` / `amdgpu` driver | same as GPU memory fields |
| **NVMe** | `/sys/class/hwmon/hwmon*/temp1_input` filtered to `nvme` driver | temp °C, read/write IOPS, MB/s (from `/proc/diskstats` deltas) |
| **Host power** | `ipmi-dcmi` (BMC) if available, else `turbostat --Summary` package power, else RAPL MSR | total system W |
| **Process** | `psutil` for the model's PID + child PIDs (from `pgrep -P` walk) | RSS, VMS, %CPU, %MEM, num threads, num FDs, GPU mem handle |
| **Wall state** | `time.time()` | monotonic clock, task elapsed, task wall-clock |

**Why this granularity matters for benchmarking local models:**

- **Power wall detection.** An RTX 3090 at 350 W cap that sustains 95 °C
  will throttle to ~280 W after 60s. A 7B model that runs at 50 tok/s
  for 30s and 35 tok/s for the next 60s is not "slower," it's *throttled*.
  Without `temp` + `power.draw` in the trace, you'd mis-score the model.
- **Token/Joule efficiency.** Local-model users care about
  performance-per-watt (laptop, edge, multi-GPU box). The benchmark
  computes `joules_per_token = mean(power.draw_W) * wall_s /
  output_tokens` and reports it per task and per category. A 7B at
  50 tok/s @ 200 W is 0.25 J/tok; the same model at 50 tok/s @ 350 W
  is 0.43 J/tok — the second is "worse" in a way a pure speed score hides.
- **Throttle regression detection.** A model upgrade that raises power
  draw and triggers throttling looks like a "regression" in raw tok/s;
  with stats we see it's a thermal issue and can advise "undervolt,
  or cap power to 280 W."
- **Cross-run reproducibility.** Same model, same task, two days apart:
  if the second run is 8% slower, was it the model? The kernel? The
  ambient temperature? Stats answers that.

**Collector design (no interference, by construction):**

- **Separate process.** `statsd` is `subprocess.Popen(['python3',
  '-m', 'hermesbench.statsd', '--out', '$stats_path', '--hz', '5'])`
  launched in parallel with hermes. It is *not* a thread, *not* in the
  hermes process — that would burn the very CPU cycles we're trying to
  measure.
- **Process priority lowered** via `os.nice(19)` + `ionice(IDLE)` on
  Linux so it never preempts the model.
- **Pinned to a single core** that the model is not using. We detect
  the model's process tree first, then choose a sibling core with the
  lowest current util. Falls back to a non-pinned collector if the
  model saturates every core (rare for inference but possible).
- **No subprocess-per-sample.** `pynvml` is used instead of
  `nvidia-smi` per sample (a fresh `nvidia-smi` invocation takes
  ~30ms — at 5 Hz that's 15% of one core just for stats). `pynvml`
  reads NVML directly in-process, no fork. Same trick for AMD:
  `amdgpu` sysfs files are read directly, no subprocess.
- **One line per sample in `.stats.jsonl`.** Schema:
  ```json
  {"t": 1700000123.456, "elapsed_s": 12.3,
   "cpu": {"pkg_temp_c": 67.2, "pkg_power_w": 142.0, "util_pct": 412.0,
           "per_core_util": [98,97,95,99,96,98,97,99, ...]},
   "gpu": [{"idx": 0, "name": "RTX 3090", "util_pct": 99, "mem_util_pct": 45,
            "temp_c": 78.0, "power_w": 318.5, "power_limit_w": 350.0,
            "clocks_gr_mhz": 1950, "clocks_mem_mhz": 9500,
            "vram_used_mib": 18234, "vram_total_mib": 24576,
            "fan_pct": 65, "pstate": "P0",
            "throttle_reasons": ["thermal_slowdown"]}],
   "ram": {"used_mib": 22100, "total_mib": 64200, "swap_mib": 0},
   "nvme": {"temp_c": 42, "read_mbs": 1.2, "write_mbs": 0.0},
   "host_power_w": 612.0,
   "model_process": {"pid": 12345, "rss_mib": 18900, "threads": 24,
                     "cpu_pct": 380.0, "gpu_mem_mib": 18200}}
  ```

**Layout addition:**

```
hermesbench/
├── statsd/
│   ├── __init__.py
│   ├── __main__.py             # `python -m hermesbench.statsd ...`
│   ├── collector.py            # main sampling loop, 5 Hz
│   ├── sources/
│   │   ├── __init__.py
│   │   ├── cpu.py              # psutil + k10temp + turbostat
│   │   ├── gpu_nvidia.py       # pynvml (in-process, no fork)
│   │   ├── gpu_amd.py          # amdgpu sysfs direct read
│   │   ├── gpu_intel.py        # i915/xe sysfs direct read
│   │   ├── memory.py           # psutil.virtual_memory
│   │   ├── nvme.py             # hwmon nvme + /proc/diskstats
│   │   ├── host_power.py       # ipmi-dcmi / RAPL MSR / turbostat
│   │   └── process.py          # model process tree RSS/threads/FDs
│   └── pinning.py              # pick a quiet core, nice/ionice the collector
```

**How it integrates with scoring:**

The scoring pipeline (`scoring.py`) joins `.stats.jsonl` with the trace
jsonl on `t` (wall-clock) and computes, per task:

- `peak_gpu_temp_c`, `peak_gpu_power_w`
- `mean_gpu_power_w`, `mean_pkg_power_w`, `mean_host_power_w`
- `throttled_seconds` (cumulative time any `throttle_reasons` was non-empty)
- `joules_per_output_token`
- `tok_per_watt` (output_tokens / mean_gpu_power_w / wall_s)
- `mean_model_cpu_cores` (median of per-core util on busy cores)

These get added to the per-task row and the per-model summary table. The
CLI prints a "thermal warning" if a run sustained `>90 °C` for >30s or
hit a `throttle_reasons` flag for >5s, so a user immediately knows if
their numbers are fair.

**How it integrates with the `.cast` overlay:**

`render` adds a small live HUD strip at the bottom of the GIF/MP4 when
the source is a paired `.stats.jsonl`:

```
[t=12s] GPU 78°C/318W tok/s: 49.2  ⚠ throttle: thermal_slowdown
[t=14s] GPU 79°C/322W tok/s: 47.1  ⚠ throttle: thermal_slowdown
...
```

The HUD is *rendered from the .stats.jsonl*, not parsed from the
terminal — it works even if the model is running headless tools that
print nothing. This is what makes the X posts "complete" — viewers see
both the model's actions and the hardware doing the work.

**X-ready visualization (pre-baked):**

`render` adds `--overlay-stats` which composes a 4-line HUD bottom strip:
```
hermesbench v0.1  |  qwen2.5-coder-7b  |  t03_patch_ambiguous  |  PASS
GPU  78°C  318W  49.2 tok/s  |  CPU 67°C 142W  |  RAM 22.1/64.2 GB  |  J/tok 0.42
```

Renders cleanly at 1080p and stays legible at X's 1080×auto downscale.

**Calibration / smoke test:**

```python
def test_statsd_runs():
    """statsd should sample for 5s and produce a valid .stats.jsonl."""
    with tempfile.TemporaryDirectory() as d:
        stats = Path(d) / "x.stats.jsonl"
        proc = subprocess.Popen(["python", "-m", "hermesbench.statsd",
                                 "--out", str(stats), "--hz", "5"])
        time.sleep(5.0)
        proc.terminate(); proc.wait(timeout=5)
        lines = [json.loads(l) for l in stats.read_text().splitlines() if l]
        assert 20 <= len(lines) <= 30, f"expected ~25 samples, got {len(lines)}"
        for sample in lines[:3]:
            assert "t" in sample and "cpu" in sample
            assert "gpu" in sample  # may be empty list if no GPU
```

**Optional integration with `intel_gpu_top`/`nvidia-smi dmon` (v0.2):**

For deep dives, `render --with-extra-overlay` can run a *second*
subprocess collector at 1 Hz that captures `nvidia-smi dmon` /
`intel_gpu_top -l -s 100` output and overlays per-SM/EFM utilization.
This is heavy and excluded from the default path.

### 3.2 The hermes-agent invocation

The benchmark runner does **not** import `AIAgent` as a library. Instead it
**spawns hermes-agent as a subprocess per task** plus a parallel
**statsd subprocess**:

```python
# hermesbench/hermes_invocation.py (sketch)
def run_task(task: TaskSpec, model: str, base_url: str) -> TaskResult:
    worktree = worktree_setup(task)
    session_name = f"hermesbench-{task.id}-{uuid4().hex[:8]}"
    isolated_home = mkdtemp(prefix="hermesbench-home-")
    trace_path = worktree / f"trace-{task.id}.jsonl"
    cast_path  = worktree / f"trace-{task.id}.cast"
    stats_path = worktree / f"trace-{task.id}.stats.jsonl"

    # Start tmux session with isolated env (records .cast via pipe-pane)
    env_overrides = {
        "TERMINAL_ENV": "tmux_isolated",
        "HERMES_TMUX_SESSION": session_name,
        "HERMES_TMUX_WORKTREE": str(worktree),
        "HERMES_TMUX_HOME": str(isolated_home),
        "HERMES_TMUX_CAST_PATH": str(cast_path),   # recorder.py reads this
        "HERMES_TMUX_NET": "off" if task.isolated_network else "on",
        "OPENAI_BASE_URL": base_url,
        "OPENAI_MODEL": model,
        "HERMES_QUIET": "1",
        "HERMES_SAVE_TRAJECTORY": "1",
        "HERMES_TRAJECTORY_PATH": str(trace_path),
    }

    # Launch statsd FIRST so we capture warmup state too
    statsd = subprocess.Popen(
        ["python3", "-m", "hermesbench.statsd",
         "--out", str(stats_path), "--hz", "5",
         "--model-name", model],
        # statsd auto-nices itself + pins to a quiet core
    )

    # Spawn hermes-agent
    proc = subprocess.Popen(
        ["python", "-m", "hermes_agent", "--print-mode", "jsonl", "--no-tui"],
        cwd=worktree, env={**os.environ, **env_overrides},
        stdout=PIPE, stderr=PIPE, text=True,
    )
    proc.stdin.write(task.prompt + "\n")
    proc.stdin.flush()

    with trace_path.open("w") as f:
        for line in proc.stdout:
            f.write(line)
    proc.wait(timeout=task.timeout_seconds)

    # Stop statsd AFTER hermes exits (so we capture clean shutdown)
    statsd.terminate(); statsd.wait(timeout=5)

    return TaskResult(trace=trace_path, cast=cast_path, stats=stats_path)
```

Key sequencing notes:
- **statsd starts *before* hermes** so we capture warmup state (model
  loading into VRAM, GPU clocks spinning up). Without this, the first
  10-20s of the run is missing from the stats trace and the
  `joules_per_output_token` calculation is biased high.
- **statsd is stopped *after* hermes exits** so we capture the model's
  clean shutdown (memory release, GPU clock downclock). Useful for
  detecting "model didn't actually release VRAM" bugs.
- **All three artifacts (`trace.jsonl`, `cast`, `stats.jsonl`) live
  in the same `worktree/`** so they're zipped/deleted together. No
  cross-reference pain.

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
- **Hardware score** (new — derived from `.stats.jsonl`):
  - `mean_gpu_power_w`, `peak_gpu_power_w`, `mean_gpu_temp_c`, `peak_gpu_temp_c`
  - `mean_cpu_power_w`, `mean_cpu_temp_c`
  - `mean_host_power_w`
  - `throttled_seconds` (cumulative time any `throttle_reasons` flag was set)
  - `joules_per_output_token` (energy per generated token)
  - `tok_per_watt` (throughput per watt — primary efficiency metric)
  - `mean_model_cpu_cores` (median per-core util — detects under-utilization)

A single model produces a results row like:

```
model: qwen2.5-coder-7b-instruct-q4_k_m
pass_rate:          28/40 (70.0%)
tool_efficiency:    median 6.1 calls/task
token_efficiency:   14,200 tok/task avg
wall_clock:         38.4 s/task avg
recovery_rate:      81.2%
format_compliance:  99.4%
--- hardware ---
gpu:                RTX 3090  mean 295W / peak 348W  mean 76°C / peak 84°C
cpu:                Ryzen 9 7950X  mean 138W  mean 64°C
host_power:         mean 612W
joules_per_tok:     0.42
tok_per_watt:       119
throttled_seconds:  0.0
mean_model_cores:   12.3 / 16 active
⚠ thermal:          none (clean run)
```

If `throttled_seconds > 5` or `peak_gpu_temp_c > 90`, the CLI prints a
**`⚠ THERMAL WARNING`** banner above the row with the recommendation
("undervolt", "cap power to 280W", "improve case airflow"). Numbers stay
in the row — the warning is advisory, not a deduction.

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

# Show hardware stats summary for a run
python -m hermesbench stats traces/qwen_t03_*.stats.jsonl
python -m hermesbench stats traces/qwen_*.stats.jsonl --summary  # per-task table
python -m hermesbench stats traces/qwen_*.stats.jsonl --plot     # save temp/power plot

# Export traces as SFT jsonl (one completion per line)
python -m hermesbench export-sft \
    --in traces/ \
    --out sft_dataset.jsonl \
    --format openai

# Render a .cast to GIF/MP4 for X (with optional stats overlay)
python -m hermesbench render traces/qwen_t03_*.cast --format gif --out tweet.gif
python -m hermesbench render traces/qwen_t03_*.cast --format mp4 \
    --add-caption "qwen2.5-coder-7b — t03_patch_ambiguous — ✅ PASS" \
    --watermark "hermesbench v0.1" \
    --overlay-stats ../traces/qwen_t03_*.stats.jsonl

# Concat multiple task casts into one reel (great for "5 tasks, 1 tweet")
python -m hermesbench render-reel traces/qwen_*.cast --format gif --out reel.gif

# Browse a recording locally before posting
python -m hermesbench play traces/qwen_t03_*.cast
```

---

## 7. Implementation phases

### Phase 1 — Skeleton + `TmuxIsolatedEnvironment` backend (Day 1-3)
- [ ] `pyproject.toml` + `hermesbench/` package skeleton
      (deps: `pyyaml`, `pyte`, `psutil`, `pynvml`, `py-cpuinfo`)
- [ ] `backend/tmux_isolated.py` — first cut: `init_session`, `_run_bash`, `cleanup`
- [ ] `backend/recorder.py` — `pyte`-based pipe-pane sink that writes
      asciinema v2 `.cast` files (80 LOC + roundtrip test)
- [ ] Wire `tmux pipe-pane` into `init_session()` so every task
      records automatically
- [ ] `backend/worktree.py` — `worktree_setup(task)` copies fixtures, sets up isolated `$HOME`
- [ ] `statsd/collector.py` + `sources/{cpu,gpu_nvidia,gpu_amd,gpu_intel,memory,nvme,host_power,process}.py`
- [ ] `statsd/pinning.py` — detect model's process tree, pick a quiet core,
      `os.nice(19)` + `ionice(IDLE)`, `taskset -c $quiet_core` on Linux
- [ ] `statsd/__main__.py` — CLI: `python -m hermesbench.statsd --out ... --hz 5`
- [ ] `runner.py` — task lifecycle: statsd first → spawn hermes → trace → teardown
- [ ] Manual smoke test: 1 task against a real model, confirm tmux session is
      created, model runs, **`.cast` is produced and re-playable**,
      **`.stats.jsonl` is produced and has all 7 metric groups**,
      tmux is killed, worktree is removed
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
- [ ] `scoring.py` computes all 6 metrics + the 9 hardware metrics
- [ ] `scoring.py` implements the `joules_per_output_token` and
      `tok_per_watt` derivations (joins trace.jsonl token counts with
      stats.jsonl power samples on `t`)
- [ ] `scoring.py` implements the thermal-warning heuristic
      (`peak_gpu_temp_c > 90` OR `throttled_seconds > 5` → warn)
- [ ] `results/<model>_<date>.json` per-run aggregate
- [ ] `cli.py` `stats` subcommand: per-task summary, `--summary` table,
      `--plot` matplotlib temp/power-over-time chart (saves PNG)
- [ ] `cli.py` `render` subcommand: `.cast` → `.gif` / `.mp4` via `agg` + `ffmpeg`,
      with `--overlay-stats` HUD strip
- [ ] `cli.py` `render-reel` subcommand: concat multiple casts
- [ ] `cli.py` `play` subcommand: `asciinema play` wrapper for local preview
- [ ] `examples/` directory seeded with 3 reference GIFs (one per
      difficulty tier: easy/medium/hard) and 3 reference stats plots
      (one clean run, one thermal-throttled run, one CPU-bound run) so
      README screenshots stay accurate when the suite evolves

### Phase 6 — Export to SFT format (Day 13)
- [ ] `export-sft` command: traces → OpenAI / ShareGPT / Hermes message formats
- [ ] Sanity check: load exported SFT jsonl, count completions, inspect a sample

### Phase 7 — Initial baseline runs (Day 14-15)
- [ ] Run against 3 representative local models: a small (3-4B), a medium (7-8B), a large (32-70B)
- [ ] Publish `results/baseline_<date>.md` in the repo with per-model
      pass rates, token efficiency, **and the full hardware table
      (mean/peak power, mean/peak temp, J/tok, tok/W, throttled_seconds)**
- [ ] For each model, commit a 4-panel stats plot: GPU power-over-time,
      GPU temp-over-time, CPU package power, RAM used — so reviewers
      can see whether the run was clean or throttled at a glance
- [ ] Commit traces (or a sample of them) so others can reproduce
- [ ] Confirm: every task's tmux session was killed, every worktree was rm-rf'd
      (post-mortem script scans `/tmp` and `tmux ls` for leaks)
- [ ] Confirm: every task's statsd was terminated cleanly
      (no orphan `python -m hermesbench.statsd` processes in `ps aux`)

### Phase 8 — v0.1 release tag (Day 16)
- [ ] README with quick-start, results table, "how to add a task" guide,
      "how to add a new environment backend" guide
- [ ] Open upstream PR to hermes-agent: register `tmux_isolated` backend
- [ ] `git tag v0.1`
- [ ] Internal dogfood: run the suite in our own dev loop for 1 week,
      fix anything that breaks

---

## 8. v0.2+ roadmap (out of scope for v0.1, listed for context)

- **v0.2 — Multi-modal + longer horizon:** vision tasks (image Q&A), browser tasks (offline mock DOM), 60-100 turn projects, **per-SM/EFM utilization via `nvidia-smi dmon` + `intel_gpu_top` extra overlay**, **ambient temperature via optional hwmon sensor**
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
- [ ] Every task run produces a valid `.cast` file (verified by
      `test_recorder_roundtrip` in CI)
- [ ] `python -m hermesbench render trace.cast --format gif` produces
      a <8MB GIF that captures the model's terminal faithfully
      (manual QA: progress bars, colors, errors all readable)
- [ ] At least 3 example X-ready GIFs are committed to
      `examples/` so users can see what the output looks like before
      running their first task
- [ ] Every task run produces a `.stats.jsonl` with all 7 metric
      groups present (CPU, GPU, RAM, NVMe, host_power, model_process,
      wall state) — verified by `test_statsd_runs` in CI
- [ ] `joules_per_output_token` and `tok_per_watt` are populated
      for every task where token count was available
- [ ] A thermal warning is printed when `peak_gpu_temp_c > 90` or
      `throttled_seconds > 5` (verified with a regression test that
      feeds synthetic stats and checks the warning logic)

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
10. **What cast format should we own long-term?** asciinema v2 (`.cast`)
    is the standard — tools like `agg`, `asciinema-player`, and `termsvg`
    all consume it. **Decision: asciinema v2 is the source of truth, GIF
    is the rendered derivative.**
11. **Does the cast include the prompt the model sees, or only its
    output?** The whole terminal — prompt + output + errors. The model's
    first user turn is `echo`-ed by hermes's print-mode anyway, so
    reviewers see "Task: fix this off-by-one" → model's response. This
    is what makes the cast self-explanatory on X. **Decision: capture
    the entire pane.**
12. **Cast file size growth?** 5-min cast ≈ 50-200 KB at 100ms tick
    with diff-based flush. 40 tasks × 5 min = ~8 MB of casts per model
    run. Acceptable for `traces/`. **Decision: keep all casts by
    default, add `.gitignore`-friendly `--keep-casts=false` for bulk
    runs.**
13. **Render server-side or via `agg` local?** `agg` is a single static
    binary, no server needed. **Decision: local render. CI uploads
    GIFs as PR artifacts.**
14. **5 Hz vs 10 Hz stats sampling?** Higher = more disk + more
    interference. **Decision: 5 Hz default, configurable 1-20 Hz via
    `--hz`. 5 Hz captures thermal transients (RTX 3090 warm-up takes
    ~20-30s) without drowning the disk.**
15. **What if `pynvml` isn't installed?** Falls back to `nvidia-smi`
    subprocess *per sample* but warns the user that it's eating ~15%
    of one core. We refuse to ship v0.1 without `pynvml` available.
    **Decision: hard dep, fail loud at install time.**
16. **What if the model has no GPU (CPU-only run)?** `statsd` still
    collects CPU/RAM/NVMe stats and the GPU section is an empty list.
    Scoring falls back to CPU-only metrics (joules per tok on package
    power). **Decision: GPU-less mode is fully supported.**
17. **RAPL MSR access requires root.** If we're not root, package
    power falls back to `turbostat` (also root) → `powertop` estimate
    → omit the field. **Decision: degrade gracefully, never crash
    the benchmark because of a stats source.**
18. **Do we record ambient temperature?** It matters for cross-run
    fairness but requires a USB sensor. **Decision: out of scope for
    v0.1. v0.2: optional `--ambient-sensor` flag for users with a
    supported hwmon device (e.g. `coretemp`-style external probe).**
19. **Should thermal warnings *deduct* from the score?** No — they
    flag, they don't penalize. The score is what the model achieved.
    Thermal state is metadata for the user to interpret.
    **Decision: advisory warnings only, no score deduction.**

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
- Stats sources verified on this host (Linux 7.0.0-15-generic):
  - `/sys/class/hwmon/` — 8 devices including `nvme`, `k10temp` (CPU),
    `amdgpu` (Intel Arc / AMD GPU), `spd5118` (RAM temp), `mt7921_phy0` (wifi)
  - `nvidia-smi` available (RTX 3090, 24GB VRAM, 350W cap)
  - `turbostat`, `script` (util-linux), `ffmpeg` all installed
  - `psutil` 7.1.0, `asciinema`/`agg`/`chafa` to be added
  - No `libtmux`, `pynvml`, `pyamdgpu` yet — to be installed via
    `pip install pynvml pyte pyyaml psutil py-cpuinfo` in Phase 1
