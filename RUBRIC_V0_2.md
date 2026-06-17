# HermesBench v0.2 Plan — Rubric Evaluation

## RUBRIC (100 points)

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Technical Correctness | 25 | Code snippets are accurate, APIs match real interfaces, no broken control flow |
| Completeness | 20 | Every referenced file/function is defined, no stubs left as `...`, every CLI command has implementation |
| Hermes-Agent Integration | 15 | Real agent spawn matches actual hermes CLI interface, trace capture works, toolset mapping is correct |
| Hyperframes/Video | 15 | tmux layout is sound, Xvfb/ffmpeg pipeline works, metrics panel is accurate, pitfalls addressed |
| Usability/Installer | 10 | install.sh works cross-platform, config system is integrated, no hardcoded user paths |
| Test/Migration | 5 | Tests for new code, backward compat, migration notes |
| Documentation | 5 | README updates, CHANGELOG, examples |
| **Total** | **100** | |

---

## SCORING

| Dimension | Score | Max | Notes |
|-----------|-------|-----|-------|
| Technical Correctness | 8 | 25 | G1-G5, G8-G11: hermes CLI is wrong, render MP4 broken, serve.py entrypoint wrong |
| Completeness | 6 | 20 | G19-G20, G22, G30: report.py, compare.py, hyperframes_launcher.sh, post-process are stubs |
| Hermes-Agent Integration | 4 | 15 | G1-G4, G11, G26: CLI invocation fundamentally wrong, trace capture mechanism wrong |
| Hyperframes/Video | 9 | 15 | G12-G15: tmux layout fragility, agent pane recursion, hardcoded paths |
| Usability/Installer | 5 | 10 | G6-G7, G14, G16, G25, G27: hardcoded paths, apt-only, config not integrated |
| Test/Migration | 1 | 5 | G17-G18, G28-G29: no tests, no migration, no loss masks |
| Documentation | 3 | 5 | G29: no CHANGELOG, README changes are bullet points only |
| **TOTAL** | **36/100** | | |

---

## GAP REGISTER (30 gaps)

### CRITICAL (blocks core functionality) — 8 gaps

**G1: Hermes CLI invocation is wrong**
- Severity: CRITICAL
- Location: WS1 §1.1, line 68-78
- Problem: Plan proposes `hermes chat -q "..." --model X --provider custom --base-url URL --yolo --no-tui`. But `--provider custom` is not valid — custom providers need `--provider custom:<name>` defined in config.yaml. `--no-tui` doesn't exist. `--toolsets` is not a `hermes chat` flag — it's configured via env or config.yaml.
- Fix: Use env vars (already set in existing code) + `-z` oneshot flag:
  ```python
  cmd = [
      str(hermes_path / "hermes"),
      "-z", task_prompt,
      "--yolo",
  ]
  # Model/endpoint set via env: OPENAI_BASE_URL, OPENAI_MODEL
  # Toolsets set via env: HERMES_TOOLSETS or via -t flag
  ```
  OR use `hermes chat -q "<prompt>" --model <model> --yolo` with `OPENAI_BASE_URL` already in env.

**G2: `--provider custom` is invalid**
- Severity: CRITICAL
- Location: WS1 §1.1, line 73
- Problem: Hermes doesn't accept `--provider custom`. Must use named providers from config or `--provider custom:<name>`.
- Fix: Remove `--provider` from cmd. Set model + base_url via env vars (already done in existing code lines 157-158).

**G3: `--no-tui` doesn't exist**
- Severity: CRITICAL
- Location: WS1 §1.1, line 76
- Problem: No such flag in hermes-agent CLI.
- Fix: Use `-z` (oneshot, inherently non-interactive) or `-q` (single query). Both exit after completion.

**G4: stdin.write is wrong for real agent**
- Severity: CRITICAL
- Location: WS1 §1.1, line 92-93
- Problem: With `-q`/`-z`, the prompt is passed as a CLI argument, not via stdin. Writing to stdin is harmless but unnecessary and misleading.
- Fix: For real agent: pass prompt via `-z <prompt>`. Remove stdin.write. For fake agent: keep stdin.write.

**G5: `--print-mode jsonl` is wrong for real agent**
- Severity: CRITICAL
- Location: WS1 §1.1, line 85 (fake block, but real block omits this entirely)
- Problem: Real hermes-agent doesn't have `--print-mode jsonl`. The trajectory is captured via `HERMES_TRAJECTORY_PATH` env var (already set on line 161). The runner.py reads stdout line-by-line — but real hermes doesn't output JSONL to stdout.
- Fix: In real agent mode, don't read stdout for trace. Read from `HERMES_TRAJECTORY_PATH` file after agent exits. Keep stdout reading only for fake mode.

**G6: `serve.py` vLLM entrypoint is wrong**
- Severity: HIGH
- Location: WS3 §3.5, line 498
- Problem: Uses `sys.executable, "-m", "vllm.entrypoints.openai.api_server"`. The correct vLLM 0.23.0 invocation is `vllm serve <model>` (the CLI command).
- Fix: `cmd = [sys.executable, "-m", "vllm", "serve", model, ...]` or use `shutil.which("vllm")`.

**G7: render.py MP4 path is broken**
- Severity: HIGH
- Location: WS3 §3.1, line 342-348
- Problem: Feeds `.cast` (asciinema JSON) directly to ffmpeg. ffmpeg cannot read this format.
- Fix: For MP4: use `agg --font-dir ... --renderer font` to produce frames, then ffmpeg. Or use `asciinema-rec` → `svg-term` → ffmpeg. Simplest: `agg` can output GIF, then ffmpeg converts GIF→MP4.

**G8: `--served-model-name` not documented in serve.py**
- Severity: HIGH
- Location: WS3 §3.5
- Problem: We hit this exact bug during VibeThinker run — vLLM model ID must match what hermesbench passes as `--model`. serve.py uses `Path(model).name` which may not match.
- Fix: Add explicit `--served-model-name` handling. If user passes `--model vibethinker-3b-nvfp4` to `hermesbench run`, the vLLM server must serve with that exact name. Config should have `model.served_name` field.

### HIGH (usability blockers) — 7 gaps

**G9: hermesbench.yaml.example has hardcoded user-specific path**
- Severity: HIGH
- Location: WS2 §2.2, line 249
- Problem: `path: /home/r0b0tdgx/vibethinker-3b-nvfp4/vibethinker-3b-nvfp4`
- Fix: Use placeholder: `path: /path/to/your/model-nvfp4`

**G10: install.sh is apt/dpkg only**
- Severity: HIGH
- Location: WS2 §2.1, line 178
- Problem: `sudo apt-get install` won't work on macOS, conda, or non-Debian Linux.
- Fix: Detect platform. Use `brew install` on macOS. Check for conda. Fall back to manual instructions if no package manager detected.

**G11: Config system not integrated into run command**
- Severity: HIGH
- Location: WS2 §2.3 + WS3 §3.4
- Problem: `load_config()` is defined but `hermesbench run` doesn't call it. `--model` and `--base-url` are always required on CLI even if config file has them.
- Fix: Make `--model` and `--base-url` optional. Fall back to config file values. `cfg = load_config(); model = model or cfg.get("model", {}).get("name")`.

**G12: 5-pane tmux layout uses split-window -p (known unreliable)**
- Severity: HIGH
- Location: WS5 §5.3, lines 1000-1015
- Problem: The live-tmux-demo-recording skill explicitly calls out that `split-window -p` is unreliable for 5+ pane layouts. Pitfall #8 in the skill.
- Fix: Use `-l <percent>%` syntax or capture pane IDs with `-P -F '#{pane_id}'` and split from those. Add verification step: `tmux list-panes -t <session> -F '#{pane_width}x#{pane_height}'` after layout.

**G13: Agent session pane has recursion bug**
- Severity: HIGH
- Location: WS5 §5.3, line 968
- Problem: `grep 'hb-'` matches the recording session (`hb-record`) itself, not just task sessions.
- Fix: `grep 'hb-' | grep -v 'hb-record'` or use a different prefix for task sessions.

**G14: record.py hardcodes `~/hermesbenchv0_1`**
- Severity: MEDIUM
- Location: WS5 §5.3, line 954
- Problem: Won't work for other users or install locations.
- Fix: Use `Path(__file__).resolve().parent.parent` (the repo root).

**G15: metrics_panel.py hardcodes tasks_total=48**
- Severity: MEDIUM
- Location: WS5 §5.2, line 732
- Problem: Task count is dynamic — repo currently has 48 but may change.
- Fix: `self.tasks_total = len(list(Path("tasks").rglob("task.yaml")))` or parse from `hermesbench list` output.

### MEDIUM (completeness gaps) — 8 gaps

**G16: report.py HTML is a stub**
- Severity: MEDIUM
- Location: WS4 §4.2, line 637
- Problem: `# ... (full template with tables, category breakdown)` — no actual HTML.
- Fix: Include full HTML template with dark theme, tables, pass/fail coloring, category breakdown. Match user's HTML preferences (flat dark bg, no gradients, overflow handling).

**G17: compare.py never defined**
- Severity: MEDIUM
- Location: WS3 §3.6 references `from hermesbench.compare import compare_runs`
- Problem: `compare_runs` function signature and implementation missing.
- Fix: Define `compare_runs(results: dict) -> str` that produces a rich Table.

**G18: compute_hardware_summary referenced but undefined**
- Severity: MEDIUM
- Location: WS3 §3.7, line 569
- Problem: `from hermesbench.scoring import compute_hardware_summary` — function doesn't exist.
- Fix: Define in scoring.py. Reads stats.jsonl from run dir, computes avg/max power, thermal AUC, throttle seconds.

**G19: hyperframes_launcher.sh listed in summary but never defined**
- Severity: MEDIUM
- Location: Summary line 38
- Problem: Referenced as a new file but no content provided.
- Fix: Either define it or remove from the file list (record.py handles this internally).

**G20: post-process command is a stub**
- Severity: MEDIUM
- Location: WS5 §5.6, line 1228
- Problem: Function body is `...`.
- Fix: Implement: ffmpeg trim (`-ss`/`-t`), thumbnail extraction (`-vframes 1`), highlight reel (multiple `-ss`/`-t` segments concatenated).

**G21: --attach/--no-attach option declared but unused**
- Severity: MEDIUM
- Location: WS5 §5.4, line 1152
- Problem: Option exists but `run()` always does headless + waits for ENTER.
- Fix: If `--attach`, skip Xvfb/ffmpeg — just create tmux session, print attach command, and exit. User records with their own tool.

**G22: sft_export.py doesn't implement loss masks**
- Severity: MEDIUM
- Location: WS3 §3.2, line 395-403
- Problem: Comment says "Loss mask: 0 for system/user/tool, 1 for assistant" but code doesn't produce them.
- Fix: Add `"loss_mask": [0 if m["role"] != "assistant" else 1 for m in messages]` to each example.

**G23: statsd/collector.py listed as modified but no changes specified**
- Severity: LOW
- Location: Summary line 24
- Problem: "expose metrics for live panel" — but what changes?
- Fix: Either specify the changes (e.g., expose a `/tmp/hb_stats.json` file for the metrics panel to read) or remove from the list.

### LOW (polish) — 7 gaps

**G24: No tests for new code**
- Severity: LOW
- Location: Entire plan
- Problem: No test files mentioned. Existing repo has `make test`.
- Fix: Add `tests/test_config.py`, `tests/test_sft_export.py`, `tests/test_scoring_v2.py`. At minimum, smoke tests for each new command.

**G25: No backward compat / migration notes**
- Severity: LOW
- Location: Entire plan
- Problem: Signature changes to `spawn_hermes()` and `run_task()` will break existing tests.
- Fix: Use keyword-only args with defaults. Add `CHANGELOG.md`.

**G26: No CHANGELOG.md**
- Severity: LOW
- Fix: Add with v0.2.0 section listing all changes.

**G27: runner.py changes are vague**
- Severity: LOW
- Location: WS1 §1.2, line 101-106
- Problem: "pass `use_real_agent=task_config.get(...)`" but doesn't show how `task_config` is constructed.
- Fix: Show the full function signature change and how `run_task` receives the flag.

**G28: serve.py health check control flow is confusing**
- Severity: LOW
- Location: WS3 §3.5, lines 522-534
- Problem: `proc.wait()` inside the health check loop — technically correct (block while server runs) but unusual pattern.
- Fix: Separate the health check (loop until ready) from the serve loop (wait for process). Add signal handling for clean shutdown.

**G29: README changes are bullet points only**
- Severity: LOW
- Location: WS6 §6.2
- Problem: "Update all CLI examples to v0.2 syntax" — no actual README content.
- Fix: Include the full Quick Start section text.

**G30: install.sh requires sudo unconditionally**
- Severity: LOW
- Location: WS2 §2.1, line 178
- Problem: `sudo apt-get` fails silently or errors on non-root users without sudo.
- Fix: Check `sudo -n true 2>/dev/null` before using sudo. If no sudo, print manual instructions.

---

## GRADE: 36/100

---

## REBUILD-TO-100 FIXES

For each gap, the concrete fix needed to bring the plan to 100/100:

### Fixes for CRITICAL gaps (G1-G8) → +21 points

**G1-G5 Fix: Complete rewrite of hermes_invocation.py real-agent section**

The fundamental issue is that the plan treats hermes-agent like a simple subprocess that reads stdin and writes JSONL to stdout. The real agent:
- Takes prompts via `-z` (oneshot) or `-q` (query) flags
- Captures trajectory via `HERMES_TRAJECTORY_PATH` env var, not stdout
- Uses `OPENAI_BASE_URL` + `OPENAI_MODEL` env vars for model config
- Uses `HERMES_TOOLSETS` or `-t` for toolset config
- Doesn't have `--print-mode`, `--no-tui`, `--provider custom`, or `--line-buffered`

Corrected WS1 §1.1:

```python
if use_real_agent:
    # Real hermes-agent: oneshot mode
    # Model/endpoint already set via OPENAI_BASE_URL + OPENAI_MODEL env vars
    # Toolsets configured via env or CLI
    toolsets = allowed_tools_to_toolsets(task_allowed_tools)
    cmd = [
        str(hermes_path / "hermes"),
        "-z", task_prompt,
        "--yolo",
        "-t", toolsets,
    ]
    cwd = str(hermes_path)
    # Trace is captured via HERMES_TRAJECTORY_PATH env var (already set)
    # stdout will contain final text output (not JSONL turns)
    proc = subprocess.Popen(cmd, cwd=cwd, env=env,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           text=True, bufsize=0)
    # No stdin.write needed — prompt is in -z flag
    return proc
```

And runner.py trace capture needs bifurcation:

```python
if use_real_agent:
    # Wait for agent to finish, then read trajectory file
    hermes_proc.wait(timeout=task.timeout_seconds)
    # Trajectory was written to HERMES_TRAJECTORY_PATH
    if trace_path.exists():
        pass  # Already written by hermes-agent
    else:
        # Fallback: capture stdout as plain text trace
        with trace_path.open("w") as f:
            f.write(hermes_proc.stdout.read())
else:
    # Fake mode: read JSONL from stdout (existing behavior)
    with trace_path.open("w") as f:
        for line in hermes_proc.stdout:
            f.write(line)
    hermes_proc.wait(timeout=task.timeout_seconds)
```

**G6 Fix: serve.py uses `vllm serve` CLI**

```python
vllm_bin = shutil.which("vllm") or sys.executable + " -m vllm"
cmd = [vllm_bin, "serve", model, "--port", str(port), ...]
```

**G7 Fix: render.py uses agg for both formats**

```python
if fmt == "gif":
    subprocess.run(["agg", str(cast), out], check=True)
elif fmt == "mp4":
    # agg → GIF, then ffmpeg GIF → MP4
    gif_tmp = str(cast.with_suffix(".gif"))
    subprocess.run(["agg", str(cast), gif_tmp], check=True)
    subprocess.run(["ffmpeg", "-y", "-i", gif_tmp, "-pix_fmt", "yuv420p",
                    "-vf", "fps=30", out], check=True)
    os.unlink(gif_tmp)
```

**G8 Fix: serve.py explicit served-model-name**

```python
# In config: model.served_name (defaults to Path(model).name)
served_name = cfg.get("model", {}).get("served_name", Path(model).name)
cmd += ["--served-model-name", served_name]
```

### Fixes for HIGH gaps (G9-G15) → +9 points

**G9:** Replace hardcoded path with `/path/to/your/model`.
**G10:** Platform detection in install.sh (apt/brew/manual).
**G11:** `--model` and `--base-url` become optional, fall back to config.
**G12:** Capture pane IDs with `-P -F '#{pane_id}'`, verify layout after creation.
**G13:** `grep 'hb-' | grep -v "$SESSION"` to exclude recording session.
**G14:** Use `Path(__file__).resolve().parent.parent` for repo root.
**G15:** `self.tasks_total = len(list(Path("tasks").rglob("task.yaml")))`.

### Fixes for MEDIUM gaps (G16-G23) → +8 points

**G16:** Full HTML template with dark theme, tables, pass/fail coloring.
**G17:** Define `compare_runs()` returning a rich Table.
**G18:** Define `compute_hardware_summary()` reading stats.jsonl.
**G19:** Remove hyperframes_launcher.sh from file list (record.py handles it).
**G20:** Implement post-process with actual ffmpeg commands.
**G21:** Implement --attach mode (create session, print attach cmd, exit).
**G22:** Add loss_mask field to SFT export.
**G23:** Remove statsd/collector.py from modified list or specify changes.

### Fixes for LOW gaps (G24-G30) → +5 points

**G24:** Add test files for config, sft_export, scoring.
**G25:** Use keyword-only args with defaults; add CHANGELOG.md.
**G26:** Add CHANGELOG.md.
**G27:** Show full function signature changes.
**G28:** Separate health check from serve loop.
**G29:** Include full Quick Start section text.
**G30:** Check sudo availability before using it.

---

## PATH TO 100/100

```
Current score:              36/100
After CRITICAL fixes (G1-G8):  57/100  (+21)
After HIGH fixes (G9-G15):     66/100  (+9)
After MEDIUM fixes (G16-G23):  74/100  (+8)
After LOW fixes (G24-G30):     79/100  (+5)
                             ────────
Remaining gap to 100:          21 points

The remaining 21 points require not just gap fixes but:
- Full HTML template implementation (not just "dark theme")     +3
- Full README.md rewrite (not bullet points)                    +3
- Actual test implementations (not just file names)             +3
- Integration test: real hermes-agent smoke test                +3
- Complete post-process implementation                          +2
- Error handling throughout (try/except, graceful degradation)  +3
- Logging strategy (how new modules log)                       +2
- Per-model configuration profiles                              +2
                              Total:                           100/100
```
