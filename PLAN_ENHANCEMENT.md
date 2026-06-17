# PLAN: HermesBench v0.1 → v0.2 Enhancement

Based on findings from running VibeThinker-3B NVFP4 through the full suite.
49 task.yaml files across 11 categories. Current codebase is a well-structured
skeleton with critical gaps between README promises and actual functionality.

---

## AUDIT FINDINGS — What's Broken or Missing

### CRITICAL (blocks core functionality)

| # | Issue | File | Impact |
|---|-------|------|--------|
| 1 | `fake_hermes.py` hardcoded as agent subprocess | hermes_invocation.py:168 | No real agent runs, no real traces, no real tool calls. This is the #1 gap. |
| 2 | `render` command documented but doesn't exist | cli.py | Users cannot convert .cast to .gif/.mp4 |
| 3 | `export-sft` command documented but doesn't exist | cli.py | Users cannot export training data |
| 4 | `archive` command documented but doesn't exist | cli.py | Users cannot archive runs |
| 5 | No `--results-dir` option on `run` | cli.py:111 | Results scatter to hardcoded results/ dir |
| 6 | `score` doesn't aggregate across run dirs | cli.py:241 | Each run dir scored independently, no summary |
| 7 | `stats` command is a stub (`TBD`) | cli.py:284 | Hardware stats inaccessible |

### HIGH (usability blockers)

| # | Issue | File | Impact |
|---|-------|------|--------|
| 8 | No install.sh / bootstrap script | repo root | `make install` uses `--break-system-packages`, no dep checks |
| 9 | No config file system | N/A | Model endpoint, tool parser, hermes path all hardcoded or env-only |
| 10 | No `--tool-call-parser` guidance | runner.py | Models need specific vLLM flags; no docs on which parser |
| 11 | `--n-runs` (variance) documented but missing | cli.py | Cannot run tasks N times for statistical significance |
| 12 | `--resume` documented but missing | cli.py | Crashed runs start from scratch |
| 13 | agg not auto-installed | doctor | GIF rendering broken on fresh machines |

### MEDIUM (polish)

| # | Issue | File | Impact |
|---|-------|------|--------|
| 14 | No per-category pass/fail summary | scoring.py | Results are flat list, no category breakdown |
| 15 | No HTML report generation | N/A | Results only in JSON, no publishable report |
| 16 | No model comparison mode | N/A | Cannot compare two models side by side |
| 17 | No vLLM launch helper | N/A | Users must figure out flags themselves |

---

## ENHANCEMENT PLAN — 6 Workstreams

### Workstream 1: Real Hermes Agent Integration (replaces fake_hermes.py)

**Goal:** Replace the fake agent subprocess with the real `hermes-agent` CLI,
capturing actual tool calls, traces, and asciinema recordings.

**Changes:**

1.1 `hermes_invocation.py` — replace `fake_hermes.py` with real hermes spawn:

```python
# BEFORE (line 168):
str(SCRIPTS / "fake_hermes.py"),

# AFTER:
str(hermes_path / "run_agent.py"),  # or the hermes CLI entrypoint
```

The real hermes-agent CLI accepts:
```
hermes chat -q "<prompt>" --model <model> --provider custom \
    --base-url <url> --toolsets terminal,file,patch,search,write,process,todo,execute_code,web,memory
```

Key flags to wire up:
- `--model` from task.yaml sampling config
- `--base-url` from --base-url CLI arg
- `--toolsets` from task.yaml allowed_tools
- `--yolo` to skip approval prompts (unattended)
- `HERMES_TRAJECTORY_PATH` env for trace capture (already set)
- `TERMINAL_ENV=tmux_isolated` (already set)

1.2 Add a `--real-agent` flag to `run` command so both modes work:
```bash
# Development/testing (fake agent):
hermesbench run --task t01_terminal_smoke/t01_echo --model fake --base-url http://localhost:8080/v1

# Production (real agent):
hermesbench run --task t01_terminal_smoke/t01_echo --model vibethinker-3b-nvfp4 \
    --base-url http://localhost:8999/v1 --real-agent
```

1.3 Map task.yaml `allowed_tools` → hermes `--toolsets`:
```python
TOOLSET_MAP = {
    "terminal": "terminal",
    "read_file": "file",
    "patch": "file",
    "search_files": "search",
    "write_file": "file",
    "process": "terminal",  # process is in terminal toolset
    "todo": "todo",
    "execute_code": "code_execution",
    "web_search": "web",
    "web_extract": "web",
    "memory": "memory",
}
```

### Workstream 2: Auto-Installer + Bootstrap

**Goal:** `curl ... | bash` that sets up everything.

2.1 `install.sh` — one-command installer:

```bash
#!/usr/bin/env bash
set -euo pipefail

echo "=== HermesBench Installer ==="

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "Installing Python 3.12..."
    sudo apt update && sudo apt install -y python3.12 python3.12-venv
fi

# Check system deps
DEPS=(tmux ffmpeg)
for dep in "${DEPS[@]}"; do
    if ! command -v "$dep" &>/dev/null; then
        echo "Installing $dep..."
        sudo apt install -y "$dep"
    fi
done

# Optional: asciinema agg (for GIF rendering)
if ! command -v agg &>/dev/null; then
    echo "agg not found (optional, for GIF rendering)"
    echo "  Install: https://github.com/asciinema/agg"
fi

# Create venv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .

# Check for hermes-agent
if [ ! -d ~/.hermes/hermes-agent ]; then
    echo "hermes-agent not found. Install: curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash"
fi

# Run doctor
python3 -m hermesbench doctor
echo ""
echo "=== Install complete ==="
echo "Run: source .venv/bin/activate && python3 -m hermesbench list"
```

2.2 Update `Makefile`:
- Replace `--break-system-packages` with venv-based install
- Add `make setup` that calls install.sh
- Add `make model-server` that launches vLLM with correct flags

2.3 `hermesbench.yaml` config file (new):
```yaml
# User-configurable defaults — edit once, use everywhere
model:
  name: vibethinker-3b-nvfp4
  base_url: http://127.0.0.1:8999/v1
  tool_call_parser: hermes  # hermes, qwen, etc.

vllm:
  # Auto-launch vLLM with these flags if server not running
  auto_launch: false
  flags:
    quantization: modelopt
    kv_cache_dtype: fp8
    attention_backend: flashinfer
    gpu_memory_utilization: 0.85
    max_model_len: 32768
    enable_auto_tool_choice: true

hermes:
  # Path to hermes-agent checkout (auto-detected if not set)
  path: ~/.hermes/hermes-agent
  yolo: true  # skip approval prompts for unattended runs

results:
  dir: ./results
  export_sft: true
  html_report: true
```

### Workstream 3: Missing CLI Commands

**Goal:** Implement every command documented in the README.

3.1 `render` command:
```python
@main.command()
@click.argument("cast_path", type=click.Path(exists=True))
@click.option("--format", "-f", type=click.Choice(["gif", "mp4"]), default="gif")
@click.option("--out", "-o", help="Output file path")
@click.option("--overlay-stats", is_flag=True, help="Overlay hardware stats HUD")
def render(cast_path, format, out, overlay_stats):
    """Render an asciinema .cast file to .gif or .mp4."""
    # Use agg for GIF, ffmpeg for MP4
    # If overlay_stats: read stats.jsonl from same dir, render HUD
```

3.2 `export-sft` command:
```python
@main.command(name="export-sft")
@click.option("--path", "-p", multiple=True, required=True, help="Run directory")
@click.option("--out", "-o", required=True, help="Output .jsonl file")
def export_sft(path, out):
    """Export conversation traces to SFT-ready JSONL with loss masks."""
    # Iterate trace.jsonl files from run dirs
    # Normalize: system/user/assistant/tool messages
    # Add loss_mask: 0 for system+user, 1 for assistant+tool
    # Write to single jsonl
```

3.3 `archive` command:
```python
@main.command()
@click.option("--path", "-p", required=True)
@click.option("--out", "-o", help="Output tar.gz path")
def archive(path, out):
    """Archive a run directory to a portable tar.gz."""
    # Pack results, traces, casts, stats into tar.gz
    # Include model name, date, hermes SHA in manifest.json
```

3.4 Add `--results-dir` to `run`:
```python
@click.option("--results-dir", "-r", default="./results", help="Output directory for results")
```

3.5 Add `--n-runs` to `run`:
```python
@click.option("--n-runs", "-n", type=int, default=1, help="Run each task N times for variance")
```

3.6 Add `--resume` to `run`:
```python
@click.option("--resume", "resume_dir", help="Resume from a previous run directory (skip completed tasks)")
```

3.7 Fix `score` to aggregate across all run dirs:
```python
@main.command()
@click.option("--path", "-p", multiple=True)
@click.option("--aggregate/--no-aggregate", default=True)
@click.option("--by-category", is_flag=True)
@click.option("--html", "-h", help="Generate HTML report")
def score(path, aggregate, by_category, html):
    """Score and summarize results."""
    # Aggregate all verifier_result.json across paths
    # Output: overall pass rate, per-category breakdown, per-difficulty
    # If --html: generate standalone HTML report
```

### Workstream 4: vLLM Launch Helper

**Goal:** One command launches a model server with correct flags.

4.1 `hermesbench serve` command:
```python
@main.command()
@click.option("--model", "-m", required=True, help="Model path or HF ID")
@click.option("--port", "-p", default=8000)
@click.option("--quantization", default=None)
@click.option("--tool-call-parser", default="hermes")
@click.option("--config", "-c", help="Path to hermesbench.yaml for defaults")
def serve(model, port, quantization, tool_call_parser, config):
    """Launch a vLLM server with benchmark-correct flags."""
    # Build the vLLM command from config + CLI args
    # Auto-detect: is this an NVFP4 model? Add --quantization modelopt
    # Add --enable-auto-tool-choice --tool-call-parser hermes
    # Add --served-model-name (basename of model path)
    # Launch as subprocess, health check, print ready
```

### Workstream 5: Model Comparison + HTML Report

5.1 `hermesbench compare` command:
```python
@main.command()
@click.option("--path", "-p", multiple=True, required=True, help="Run directories to compare")
@click.option("--html", "-o", help="Output HTML report path")
def compare(path, html):
    """Compare results across multiple model runs."""
    # Side-by-side table: model, pass rate, per-category, avg wall clock
    # If --html: generate standalone HTML with comparison tables + charts
```

5.2 HTML report generator (`hermesbench/report.py`):
- Dark theme (per user preference)
- Pass/fail table per task, per category, per difficulty
- Hardware telemetry charts (if stats.jsonl exists)
- Mobile-compatible, overflow handling
- Flat dark background, no gradients

### Workstream 6: Task System Enhancements

6.1 Per-category pass/fail in scoring:
```python
# Group by category prefix (t01_, t02_, etc.)
# Report: t01_terminal_smoke: 2/5 (40%)
```

6.2 Difficulty-weighted scoring:
```python
# Difficulty 1: 1 point, Difficulty 2: 2 points, Difficulty 3: 3 points
# Weighted score = sum(points_passed) / sum(points_total)
```

6.3 Model capability profile:
```python
# Based on pass/fail pattern, report:
# "This model can: terminal (basic), file_read (basic), patch (basic)"
# "This model cannot: process management, todo, execute_code, web, memory"
```

---

## IMPLEMENTATION PRIORITY

```
Phase 1 (Core Fix):     Workstream 1 (real agent) + Workstream 3 (CLI gaps)
Phase 2 (Usability):    Workstream 2 (installer) + Workstream 4 (serve helper)
Phase 3 (Polish):       Workstream 5 (compare/report) + Workstream 6 (scoring)
```

## FILE CHANGE MAP

```
Files to modify:
  hermesbench/cli.py              — add 6 commands, add --results-dir/--n-runs/--resume
  hermesbench/hermes_invocation.py — swap fake_hermes.py for real agent
  hermesbench/runner.py           — wire new options, real agent mode
  hermesbench/scoring.py          — aggregation, per-category, difficulty weighting
  Makefile                        — venv install, make setup, make serve
  pyproject.toml                  — add optional deps (jinja2 for HTML reports)

Files to create:
  install.sh                      — bootstrap installer
  hermesbench.yaml.example        — config template
  hermesbench/serve.py            — vLLM launch helper
  hermesbench/report.py           — HTML report generator
  hermesbench/compare.py          — model comparison
  hermesbench/sft_export.py       — SFT trace export
  hermesbench/render.py           — asciinema → gif/mp4 renderer
```

## DELIVERABLE

A forked/PR'd repo where:

```bash
# Zero to running in 3 commands:
./install.sh
hermesbench serve --model vibethinker-3b-nvfp4 --port 8999
hermesbench run --all --model vibethinker-3b-nvfp4 --base-url http://localhost:8999/v1

# Then analyze:
hermesbench score --path results/vibethinker* --by-category --html report.html
hermesbench compare --path results/model_a --path results/model_b --html comparison.html
hermesbench export-sft --path results/vibethinker* --out training_data.jsonl
hermesbench render traces/t01_echo/trace.cast --format gif --out demo.gif
```
