# IMPLEMENTATION PLAN: HermesBench v0.2

## In-place upgrade of am423/hermesbenchv0_1

Branch: `v0.2` → PR → merge to `main`
Version bump: 0.1.0 → 0.2.0
Tag: `v0.2.0`

---

## SUMMARY OF CHANGES

```
Files modified (10):
  pyproject.toml                    version bump, new deps
  Makefile                          venv install, make setup, make serve
  README.md                         update for v0.2
  hermesbench/__init__.py           version 0.2.0
  hermesbench/cli.py                +7 commands, +4 options on run
  hermesbench/hermes_invocation.py  real agent spawn + fake fallback
  hermesbench/runner.py             wire new options, real agent path
  hermesbench/scoring.py            aggregation, per-category, difficulty
  hermesbench/types.py              new config types
  hermesbench/statsd/collector.py   expose metrics for live panel

Files created (12):
  install.sh                        bootstrap installer
  hermesbench.yaml.example          config template
  hermesbench/serve.py              vLLM launch helper
  hermesbench/report.py             HTML report generator
  hermesbench/sft_export.py         SFT trace exporter
  hermesbench/render.py             asciinema → gif/mp4
  hermesbench/config.py             config file loader
  hermesbench/compare.py            model comparison
  hermesbench/record.py             hyperframes video orchestrator
  hermesbench/metrics_panel.py      live GPU/vLLM telemetry panel
  scripts/record_tmux.sh            Xvfb+xterm+ffmpeg capture wrapper
  scripts/hyperframes_launcher.sh   armed 5-pane tmux session builder
```

---

## WORKSTREAM 1: Real Hermes Agent Integration

### 1.1 hermes_invocation.py — dual mode (fake + real)

Current line 168 hardcodes fake_hermes.py. Replace with a mode switch:

```python
# hermes_invocation.py

USE_REAL_AGENT = os.environ.get("HERMESBENCH_REAL_AGENT", "0") == "1"

def spawn_hermes(*, hermes_path, task_prompt, worktree, isolated_home,
                 cast_path, model, base_url, env_overrides, timeout_seconds=180,
                 use_real_agent=False):
    """Spawn hermes-agent (real or fake) as a subprocess."""

    env = {
        **os.environ,
        "TERMINAL_ENV": "tmux_isolated",
        "HERMES_TMUX_SESSION": f"hb-{worktree.name}",
        ...
    }

    if use_real_agent or USE_REAL_AGENT:
        # Real hermes-agent: use the CLI
        cmd = [
            str(hermes_path / "hermes"),  # or sys.executable, str(hermes_path / "cli.py")
            "chat",
            "-q", task_prompt,
            "--model", model,
            "--provider", "custom",
            "--base-url", base_url,
            "--yolo",  # unattended: skip approval prompts
            "--no-tui",
            "--toolsets", env_overrides.get("ALLOWED_TOOLSETS", "terminal,file,patch,search,write,process,todo,execute_code,web,memory"),
        ]
        cwd = str(hermes_path)
    else:
        # Fake hermes (backward compat for development/testing)
        cmd = [
            sys.executable, "-u",
            str(SCRIPTS / "fake_hermes.py"),
            "--print-mode", "jsonl",
            "--no-tui",
            "--line-buffered",
        ]
        cwd = hermes_path

    proc = subprocess.Popen(cmd, cwd=cwd, env=env, ...)
    proc.stdin.write(task_prompt + "\n")
    proc.stdin.flush()
    return proc
```

### 1.2 runner.py — wire the mode flag

In `run_task()`, pass `use_real_agent` down:

```python
# Line ~224, where spawn_hermes is called:
hermes_proc = spawn_hermes(
    ...
    use_real_agent=task_config.get("use_real_agent", False),
)
```

### 1.3 cli.py — add `--real-agent` flag to run

```python
@click.option("--real-agent", is_flag=True,
              help="Use real hermes-agent instead of fake_hermes.py")
def run(..., real_agent):
    ...
    os.environ["HERMESBENCH_REAL_AGENT"] = "1" if real_agent else "0"
```

### 1.4 Tool mapping — task.yaml allowed_tools → hermes toolsets

Add to hermes_invocation.py:

```python
TOOLSET_MAP = {
    "terminal": "terminal",
    "read_file": "file",
    "patch": "file",
    "search_files": "search",
    "write_file": "file",
    "process": "terminal",
    "todo": "todo",
    "execute_code": "code_execution",
    "web_search": "web",
    "web_extract": "web",
    "memory": "memory",
}

def allowed_tools_to_toolsets(allowed_tools: list[str]) -> str:
    toolsets = set()
    for tool in allowed_tools:
        if tool in TOOLSET_MAP:
            toolsets.add(TOOLSET_MAP[tool])
    return ",".join(sorted(toolsets))
```

---

## WORKSTREAM 2: Auto-Installer

### 2.1 install.sh

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "╔══════════════════════════════════════╗"
echo "║  HermesBench v0.2 Installer          ║"
echo "╚══════════════════════════════════════╝"

# 1. Python check (3.11+)
PYVER=$(python3 -c 'import sys; print(sys.version_info >= (3,11))')
if [ "$PYVER" != "True" ]; then
    echo "⚠  Python 3.11+ required. Found: $(python3 --version 2>&1)"
    echo "  Install: sudo apt install python3.12 python3.12-venv"
    exit 1
fi
echo "✓ Python $(python3 --version 2>&1)"

# 2. System deps
for dep in tmux ffmpeg; do
    if command -v "$dep" &>/dev/null; then
        echo "✓ $dep"
    else
        echo "→ Installing $dep..."
        sudo apt-get update -qq && sudo apt-get install -y -qq "$dep"
        echo "✓ $dep installed"
    fi
done

# 3. Optional: agg (asciinema GIF renderer)
if ! command -v agg &>/dev/null; then
    echo "ℹ  agg not found (optional: for .cast → .gif rendering)"
    echo "   Install: cargo install agg  OR  https://github.com/asciinema/agg"
fi

# 4. Create venv + install
echo "→ Creating virtual environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -e . -q
echo "✓ Python dependencies installed"

# 5. Check for hermes-agent
HERMES_FOUND=false
for path in ~/.hermes/hermes-agent ~/hermes-agent ./hermes-agent; do
    if [ -d "$path" ]; then
        echo "✓ hermes-agent found at $path"
        HERMES_FOUND=true
        export HERMES_AGENT_PATH="$path"
        break
    fi
done
if [ "$HERMES_FOUND" = "false" ]; then
    echo "⚠  hermes-agent not found."
    echo "   Install: curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash"
    echo "   Or set:  export HERMES_AGENT_PATH=/path/to/hermes-agent"
fi

# 6. Doctor check
echo ""
echo "→ Running doctor check..."
python3 -m hermesbench doctor || true

# 7. Config template
if [ ! -f hermesbench.yaml ]; then
    cp hermesbench.yaml.example hermesbench.yaml
    echo "✓ Created hermesbench.yaml (edit to configure your model)"
fi

echo ""
echo "╔══════════════════════════════════════╗"
echo "║  Installation complete!              ║"
echo "╠══════════════════════════════════════╣"
echo "║  Next steps:                         ║"
echo "║  1. Edit hermesbench.yaml            ║"
echo "║  2. hermesbench serve                ║"
echo "║  3. hermesbench run --all            ║"
echo "╚══════════════════════════════════════╝"
```

### 2.2 hermesbench.yaml.example

```yaml
# HermesBench v0.2 Configuration
# Copy to hermesbench.yaml and edit.

model:
  name: vibethinker-3b-nvfp4
  base_url: http://127.0.0.1:8999/v1
  tool_call_parser: hermes  # hermes, qwen, deepseek_r1

# vLLM auto-launch (optional — skip if you manage vLLM separately)
vllm:
  auto_launch: false
  path: /home/r0b0tdgx/vibethinker-3b-nvfp4/vibethinker-3b-nvfp4
  port: 8999
  flags:
    quantization: modelopt
    kv-cache-dtype: fp8
    attention-backend: flashinfer
    gpu-memory-utilization: 0.85
    max-model-len: 32768
    enable-auto-tool-choice: true
    tool-call-parser: hermes

# hermes-agent
hermes:
  path: ~/.hermes/hermes-agent
  real_agent: false  # set true to use real hermes-agent (requires --real-agent on run)

# Results
results:
  dir: ./results
  html_report: true
  export_sft: true

# Run options
run:
  timeout_seconds: 120
  max_turns: 10
```

### 2.3 config.py — config loader

```python
"""hermesbench/config.py — load hermesbench.yaml defaults."""
from pathlib import Path
from typing import Any
import yaml

DEFAULT_CONFIG_PATHS = [
    Path.cwd() / "hermesbench.yaml",
    Path.home() / ".hermesbench.yaml",
]

def load_config(path: str | None = None) -> dict[str, Any]:
    """Load config from hermesbench.yaml. Returns {} if not found."""
    paths = [Path(path)] if path else DEFAULT_CONFIG_PATHS
    for p in paths:
        if p.exists():
            with open(p) as f:
                return yaml.safe_load(f) or {}
    return {}
```

### 2.4 Makefile updates

```makefile
install:
	./install.sh

setup:
	./install.sh

serve:
	python3 -m hermesbench serve $(MODEL) --port $(PORT)

run-all:
	python3 -m hermesbench run --all --model $(MODEL) --base-url $(BASE_URL)
```

---

## WORKSTREAM 3: Missing CLI Commands

### 3.1 render command

```python
# hermesbench/render.py
"""Render asciinema .cast to .gif or .mp4."""
import subprocess, shutil
from pathlib import Path

def render_cast(cast_path: str, fmt: str = "gif", out: str | None = None,
                overlay_stats: bool = False) -> str:
    cast = Path(cast_path)
    if not cast.exists():
        raise FileNotFoundError(f"Cast file not found: {cast}")

    if not out:
        out = str(cast.with_suffix(f".{fmt}"))

    if fmt == "gif":
        if not shutil.which("agg"):
            raise RuntimeError("agg not installed. See: https://github.com/asciinema/agg")
        subprocess.run(["agg", str(cast), out], check=True)
    elif fmt == "mp4":
        # Pipe asciinema through asciinema2gif or use ttyrec → ffmpeg
        subprocess.run([
            "ffmpeg", "-y", "-i", str(cast),
            "-vf", "fps=30",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p", out
        ], check=True)

    return out
```

CLI registration in cli.py:

```python
@main.command()
@click.argument("cast_path", type=click.Path(exists=True))
@click.option("--format", "-f", type=click.Choice(["gif", "mp4"]), default="gif")
@click.option("--out", "-o", help="Output file path")
@click.option("--overlay-stats", is_flag=True)
def render(cast_path, format, out, overlay_stats):
    """Render an asciinema .cast file to .gif or .mp4."""
    from hermesbench.render import render_cast
    result = render_cast(cast_path, format, out, overlay_stats)
    click.echo(f"Rendered: {result}")
```

### 3.2 export-sft command

```python
# hermesbench/sft_export.py
"""Export conversation traces to SFT-ready JSONL."""

def export_sft(run_paths: list[str], out_path: str) -> int:
    """Export all traces from run dirs to a single SFT JSONL.
    Returns number of examples written.
    """
    examples = []
    for run_path in run_paths:
        p = Path(run_path)
        # Find trace.jsonl files
        for trace_file in p.rglob("trace.jsonl"):
            messages = []
            with open(trace_file) as f:
                for line in f:
                    if not line.strip():
                        continue
                    msg = json.loads(line)
                    messages.append(msg)

            if not messages:
                continue

            # Build SFT example
            # Loss mask: 0 for system/user/tool, 1 for assistant
            formatted = {
                "messages": [
                    {"role": m["role"], "content": m.get("content", "")}
                    for m in messages
                ],
                "source": str(trace_file),
            }
            examples.append(formatted)

    with open(out_path, "w") as f:
        for ex in examples:
            f.write(json.dumps(ex) + "\n")

    return len(examples)
```

CLI:

```python
@main.command(name="export-sft")
@click.option("--path", "-p", multiple=True, required=True)
@click.option("--out", "-o", required=True)
def export_sft(path, out):
    """Export conversation traces to SFT-ready JSONL."""
    from hermesbench.sft_export import export_sft as do_export
    count = do_export(list(path), out)
    click.echo(f"Exported {count} examples to {out}")
```

### 3.3 score — aggregate + per-category + HTML

```python
@main.command()
@click.option("--path", "-p", multiple=True, required=True)
@click.option("--by-category", is_flag=True, help="Break down by task category")
@click.option("--by-difficulty", is_flag=True, help="Weight by difficulty")
@click.option("--html", "-h", help="Generate HTML report at this path")
def score(path, by_category, by_difficulty, html):
    """Score and summarize results across one or more runs."""
    from hermesbench.scoring import aggregate_results, category_breakdown
    from hermesbench.report import generate_html_report

    all_results = aggregate_results(list(path))

    # Overall
    total = len(all_results)
    passed = sum(1 for r in all_results if r["status"] == "PASS")
    rate = passed / total * 100 if total else 0

    click.echo(f"\nOverall: {passed}/{total} ({rate:.1f}%)")

    if by_category:
        cats = category_breakdown(all_results)
        for cat, (p, t) in sorted(cats.items()):
            click.echo(f"  {cat:<30} {p}/{t} ({p/t*100:.0f}%)")

    if html:
        generate_html_report(all_results, html)
        click.echo(f"HTML report: {html}")
```

### 3.4 Additional run options

```python
@click.option("--results-dir", "-r", default="./results",
              help="Output directory for results")
@click.option("--n-runs", "-n", type=int, default=1,
              help="Run each task N times for variance measurement")
@click.option("--resume", "resume_dir",
              help="Resume from a previous run (skip completed tasks)")
```

### 3.5 serve command

```python
@main.command()
@click.option("--model", "-m", required=True)
@click.option("--port", "-p", default=8999)
@click.option("--quantization", default=None)
@click.option("--config", "-c", default=None)
def serve(model, port, quantization, config):
    """Launch a vLLM server with benchmark-correct flags."""
    from hermesbench.serve import launch_vllm
    launch_vllm(model, port, quantization, config)
```

```python
# hermesbench/serve.py
"""vLLM launch helper for hermesbench."""

def launch_vllm(model: str, port: int = 8999, quantization: str | None = None,
                config_path: str | None = None):
    import subprocess, sys, time, urllib.request

    # Load config
    from hermesbench.config import load_config
    cfg = load_config(config_path)
    vllm_cfg = cfg.get("vllm", {})
    flags = vllm_cfg.get("flags", {})

    # Build command
    cmd = [
        sys.executable, "-m", "vllm.entrypoints.openai.api_server",
        "--model", model,
        "--port", str(port),
        "--served-model-name", Path(model).name,
        "--host", "0.0.0.0",
    ]

    if quantization or flags.get("quantization"):
        cmd += ["--quantization", quantization or flags["quantization"]]
    if flags.get("kv-cache-dtype") or flags.get("kv_cache_dtype"):
        cmd += ["--kv-cache-dtype", flags.get("kv-cache-dtype", flags.get("kv_cache_dtype"))]
    if flags.get("attention-backend") or flags.get("attention_backend"):
        cmd += ["--attention-backend", flags.get("attention-backend", flags.get("attention_backend"))]
    if flags.get("enable-auto-tool-choice", flags.get("enable_auto_tool_choice", False)):
        cmd += ["--enable-auto-tool-choice"]
    parser = flags.get("tool-call-parser", flags.get("tool_call_parser", "hermes"))
    cmd += ["--tool-call-parser", parser]

    # Always good defaults
    cmd += ["--enforce-eager", "--trust-remote-code", "--enable-prefix-caching"]

    print(f"Launching vLLM: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd)

    # Health check
    for i in range(90):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2)
            print(f"\n✓ vLLM ready on port {port}")
            print(f"  Model: {Path(model).name}")
            print(f"  Base URL: http://127.0.0.1:{port}/v1")
            print(f"\n  Run: hermesbench run --all --model {Path(model).name} --base-url http://127.0.0.1:{port}/v1")
            proc.wait()
        except:
            time.sleep(2)
    print("✗ vLLM failed to start within 180s")
    proc.terminate()
```

### 3.6 compare command

```python
@main.command()
@click.option("--path", "-p", multiple=True, required=True,
              help="Run directories to compare (at least 2)")
@click.option("--html", "-o", help="Output HTML comparison report")
def compare(path, html):
    """Compare results across multiple model runs."""
    from hermesbench.compare import compare_runs
    from hermesbench.report import generate_comparison_html

    results = {}
    for p in path:
        from hermesbench.scoring import aggregate_results
        results[p] = aggregate_results([p])

    table = compare_runs(results)
    click.echo(table)

    if html:
        generate_comparison_html(results, html)
        click.echo(f"HTML report: {html}")
```

### 3.7 Fix stats command (currently stub)

```python
@main.command()
@click.option("--path", "-p", required=True, help="Run directory")
def stats(path):
    """Show hardware stats summary for a run."""
    from hermesbench.scoring import compute_hardware_summary
    summary = compute_hardware_summary(path)
    # Print formatted table
    click.echo(f"Run: {path}")
    for key, val in summary.items():
        click.echo(f"  {key}: {val}")
```

---

## WORKSTREAM 4: Scoring Enhancements

### 4.1 scoring.py — aggregation

```python
def aggregate_results(run_paths: list[str]) -> list[dict]:
    """Collect all verifier_result.json across run dirs."""
    results = []
    for run_path in run_paths:
        for f in Path(run_path).rglob("verifier_result.json"):
            with open(f) as fh:
                d = json.load(fh)
                d["run_path"] = run_path
                results.append(d)
    return results

def category_breakdown(results: list[dict]) -> dict[str, tuple[int, int]]:
    """Group by category prefix (t01_, t02_, etc.)."""
    cats = {}
    for r in results:
        cat = r["task_id"].rsplit("/", 1)[0]
        if cat not in cats:
            cats[cat] = [0, 0]  # [passed, total]
        cats[cat][1] += 1
        if r["status"] == "PASS":
            cats[cat][0] += 1
    return {k: (v[0], v[1]) for k, v in cats.items()}

def difficulty_weighted(results: list[dict], difficulty_map: dict[str, int]) -> float:
    """Weight by difficulty: d1=1pt, d2=2pt, d3=3pt."""
    earned = sum(d * difficulty_map.get(r["task_id"], 1)
                 for r in results if r["status"] == "PASS")
    total = sum(d * difficulty_map.get(r["task_id"], 1) for r in results)
    return earned / total if total else 0
```

### 4.2 report.py — HTML report generator

```python
# hermesbench/report.py
"""Generate standalone HTML reports for benchmark results."""

def generate_html_report(results: list[dict], out_path: str, model_name: str = ""):
    """Generate a dark-themed HTML report with pass/fail tables."""

    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    rate = passed / total * 100 if total else 0

    cats = {}
    for r in results:
        cat = r["task_id"].rsplit("/", 1)[0]
        cats.setdefault(cat, {"pass": 0, "total": 0})
        cats[cat]["total"] += 1
        if r["status"] == "PASS":
            cats[cat]["pass"] += 1

    # Build HTML with dark theme, no gradients, mobile-compatible
    # ... (full template with tables, category breakdown)
    Path(out_path).write_text(html)

def generate_comparison_html(results: dict[str, list], out_path: str):
    """Side-by-side HTML comparison of multiple model runs."""
    ...
```

---

## WORKSTREAM 5: Hyperframes Video Capture

**Goal:** `hermesbench record` — one command launches a multi-pane tmux session
that captures the benchmark running live, with real-time GPU telemetry, power
draw, thermals, task progress, and agent tool calls on screen. Outputs an MP4
ready for social/X sharing.

This workstream depends on Workstream 1 (real agent) — the video shows real
agent terminal sessions. With fake_hermes.py there is nothing to capture.

### 5.1 Architecture — 5-pane tmux session

```
┌──────────────────────────┬───────────────────────┐
│                          │                       │
│   PANE 1: Runner         │   PANE 2: Metrics     │
│   Task progress          │   GPU Util: 72%       │
│   t01_echo... PASS       │   Temp:    48°C       │
│   t02_ls... FAIL         │   Power:   22W        │
│   t03_compile... PASS    │   VRAM:   4.2/128 GB  │
│   [12/48] 25% ...        │   Decode:  71 tok/s   │
│                          │   Cache:   87% hit    │
│                          │   Throttle: 0s        │
├──────────────────────────┼───────────────────────┤
│                          │                       │
│   PANE 3: Agent Session  │   PANE 4: Scoreboard  │
│   (live tmux from        │   PASS: 10  FAIL: 2   │
│    current task)         │   Cat: t01 2/5 (40%)  │
│   > terminal: echo hi    │   Cat: t02 3/6 (50%)  │
│   < hello                │   Cat: t03 1/5 (20%)  │
│   > patch fix.py         │   J/tok: 0.31         │
│   < applied              │   Thermal AUC: 47.2   │
│                          │                       │
├──────────────────────────┴───────────────────────┤
│                                                  │
│   PANE 5: Telemetry Strip (full width)           │
│   ▁▂▃▅▆▇█▇▆▅▃▂  GPU%   ▏▎▍▎▌▎▍▎  Power(W)       │
│   48°C ●●●○○  Thermal zones                       │
│                                                  │
└──────────────────────────────────────────────────┘
```

### 5.2 hermesbench/metrics_panel.py — live telemetry renderer

Extends the template from `live-tmux-demo-recording` skill with:

- nvidia-smi polling at 2 Hz (GPU util, temp, power, VRAM, throttle)
- vLLM /metrics polling at 1 Hz (decode tok/s, cache hit, queue depth)
- hermesbench runner log parsing (task progress, pass count, category tally)
- Sparkline rendering for power/temp history (last 60 samples)
- Thermal zone status (green/amber/red based on temp thresholds)
- Joules-per-token calculation (cumulative energy / cumulative tokens)
- Elapsed time + ETA based on avg task duration

```python
# hermesbench/metrics_panel.py
"""Live metrics panel for hermesbench hyperframes video capture.

Polls GPU telemetry, vLLM metrics, and hermesbench runner log.
Renders a compact dashboard suitable for tmux pane display.
"""
import os, re, subprocess, sys, time, json, urllib.request
from collections import deque
from pathlib import Path

class MetricsPanel:
    def __init__(self, vllm_url="http://127.0.0.1:8999",
                 runner_log=None, results_dir=None,
                 update_hz=2, brand="@mr-r0b0t"):
        self.vllm_url = vllm_url.rstrip("/")
        self.runner_log = runner_log
        self.results_dir = results_dir
        self.interval = 1.0 / update_hz
        self.brand = brand
        self.history = {
            "gpu_util": deque(maxlen=60),
            "power": deque(maxlen=60),
            "temp": deque(maxlen=60),
        }
        self.energy_joules = 0.0
        self.tokens_generated = 0
        self.last_power = 0.0
        self.last_time = time.time()
        self.tasks_done = 0
        self.tasks_pass = 0
        self.tasks_total = 48
        self.start_time = time.time()
        self.current_task = ""

    def poll_gpu(self):
        """nvidia-smi query."""
        try:
            out = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu,"
                 "power.draw,memory.used,memory.total,clocks_throttle_reasons.active",
                 "--format=csv,noheader,nounits"], text=True, timeout=5)
            p = out.strip().split(",")
            return {
                "util": int(p[0].strip()),
                "temp": int(p[1].strip()),
                "power": float(p[2].strip()),
                "mem_used": int(p[3].strip()),
                "mem_total": int(p[4].strip()),
                "throttle": p[5].strip() if len(p) > 5 else "0",
            }
        except: return None

    def poll_vllm(self):
        """vLLM /metrics endpoint."""
        try:
            with urllib.request.urlopen(f"{self.vllm_url}/metrics", timeout=3) as r:
                text = r.read().decode()
            m = {}
            for line in text.splitlines():
                if "vllm:avg_generation_throughput" in line and not line.startswith("#"):
                    v = re.search(r'\s+([\d.]+)$', line)
                    if v: m["decode_tps"] = float(v.group(1))
                elif "vllm:gpu_cache_usage_perc" in line and not line.startswith("#"):
                    v = re.search(r'\s+([\d.]+)$', line)
                    if v: m["cache_usage"] = float(v.group(1))
                elif "vllm:prompt_tokens_total" in line:
                    v = re.search(r'\s+(\d+)$', line)
                    if v: m["prompt_tokens"] = int(v.group(1))
                elif "vllm:generation_tokens_total" in line:
                    v = re.search(r'\s+(\d+)$', line)
                    if v: m["gen_tokens"] = int(v.group(1))
            return m
        except: return {}

    def parse_runner_log(self):
        """Track task progress from hermesbench runner output."""
        if not self.runner_log or not os.path.exists(self.runner_log):
            return
        try:
            with open(self.runner_log) as f:
                lines = f.readlines()
            self.tasks_pass = sum(1 for l in lines if "PASS" in l)
            fail = sum(1 for l in lines if "FAIL" in l)
            self.tasks_done = self.tasks_pass + fail
            for l in reversed(lines):
                m = re.match(r'\s*-> (.+?)\.\.\.', l)
                if m:
                    self.current_task = m.group(1)
                    break
        except: pass

    def update_energy(self, gpu):
        """Accumulate joules from power readings."""
        now = time.time()
        dt = now - self.last_time
        self.energy_joules += self.last_power * dt
        self.last_power = gpu.get("power", 0) if gpu else 0
        self.last_time = now

    def sparkline(self, data, width=20, fill="▁▂▃▄▅▆▇█"):
        """Render a sparkline from a deque of values."""
        if not data: return ""
        lo, hi = min(data), max(data)
        if hi == lo: return fill[3] * min(len(data), width)
        scaled = [int((v - lo) / (hi - lo) * (len(fill) - 1)) for v in data]
        trimmed = scaled[-width:]
        return "".join(fill[i] for i in trimmed)

    def render(self):
        """Render the full panel."""
        gpu = self.poll_gpu()
        vllm = self.poll_vllm()
        self.parse_runner_log()

        if gpu:
            self.history["gpu_util"].append(gpu["util"])
            self.history["power"].append(gpu["power"])
            self.history["temp"].append(gpu["temp"])
            self.update_energy(gpu)
            if "gen_tokens" in vllm:
                self.tokens_generated = vllm["gen_tokens"]

        elapsed = time.time() - self.start_time
        pct = self.tasks_done / self.tasks_total * 100 if self.tasks_total else 0
        eta = (elapsed / self.tasks_done * (self.tasks_total - self.tasks_done)
               if self.tasks_done > 0 else 0)
        jpt = (self.energy_joules / self.tokens_generated
               if self.tokens_generated > 0 else 0)

        os.system('clear')
        W = 44  # panel width
        print("╔" + "═" * W + "╗")
        print("║" + f"  🔥 Live Telemetry — {self.brand}".ljust(W + 2) + "║")
        print("╠" + "═" * W + "╣")

        if gpu:
            print("║" + f"  GPU Util: {gpu['util']:>3}%    "
                  f"Temp: {gpu['temp']:>3}°C    "
                  f"Power: {gpu['power']:>5.1f}W".ljust(W + 2) + "║")
            print("║" + f"  VRAM:     {gpu['mem_used']:>6}/{gpu['mem_total']} MB"
                  .ljust(W + 2) + "║")
        else:
            print("║" + "  GPU: unavailable".ljust(W + 2) + "║")

        print("║" + f"  Decode:   {vllm.get('decode_tps', 0):>6.1f} tok/s"
              .ljust(W + 2) + "║")
        print("║" + f"  Cache:    {vllm.get('cache_usage', 0)*100:>5.1f}% hit"
              .ljust(W + 2) + "║")

        throttle = gpu.get("throttle", "0") if gpu else "0"
        throt_s = "NONE" if throttle in ("0", "Not Active", "[Not Active]") else throttle[:20]
        print("║" + f"  Throttle: {throt_s}".ljust(W + 2) + "║")

        print("╠" + "═" * W + "╣")
        print("║" + f"  Task:     {self.tasks_done}/{self.tasks_total} ({pct:.0f}%)"
              .ljust(W + 2) + "║")
        print("║" + f"  Passed:   {self.tasks_pass}/{self.tasks_done}"
              .ljust(W + 2) + "║")
        print("║" + f"  Current:  {self.current_task[:W-12]}".ljust(W + 2) + "║")
        print("║" + f"  Elapsed:  {elapsed/60:.1f}m    ETA: {eta/60:.1f}m"
              .ljust(W + 2) + "║")

        print("╠" + "═" * W + "╣")
        print("║" + "  GPU% " + self.sparkline(self.history["gpu_util"]).ljust(W - 6)
              + "║")
        print("║" + "  PWR  " + self.sparkline(self.history["power"]).ljust(W - 6)
              + "║")
        print("║" + "  TEMP " + self.sparkline(self.history["temp"]).ljust(W - 6)
              + "║")

        print("╠" + "═" * W + "╣")
        print("║" + f"  Energy:   {self.energy_joules/1000:>7.1f} kJ total"
              .ljust(W + 2) + "║")
        print("║" + f"  J/token:  {jpt:>7.3f} J".ljust(W + 2) + "║")
        print("╚" + "═" * W + "╝")

        sys.stdout.flush()

    def run(self):
        while True:
            self.render()
            time.sleep(self.interval)
```

### 5.3 hermesbench/record.py — hyperframes orchestrator

```python
# hermesbench/record.py
"""Hyperframes video capture: multi-pane tmux session + Xvfb + ffmpeg.

Creates a 5-pane armed tmux session, waits for user to start recording,
then fires the trigger to run the benchmark with live capture.

Usage:
    hermesbench record --model vibethinker-3b-nvfp4 \\
        --base-url http://127.0.0.1:8999/v1 \\
        --output hyperframes.mp4 --duration 1800
"""
import os, subprocess, sys, time, signal
from pathlib import Path

PANE_LAYOUT = """
┌──────────────────────┬───────────────────┐
│                      │                   │
│  Pane 1: Runner      │  Pane 2: Metrics  │
│  (55% w, 45% h)      │  (45% w, 45% h)   │
│                      │                   │
├──────────────────────┼───────────────────┤
│                      │                   │
│  Pane 3: Agent       │  Pane 4: Score    │
│  (55% w, 40% h)      │  (45% w, 40% h)   │
│                      │                   │
├──────────────────────┴───────────────────┤
│  Pane 5: Telemetry Strip                 │
│  (100% w, 15% h)                         │
└──────────────────────────────────────────┘
"""

class HyperframesRecorder:
    def __init__(self, model, base_url, output="hyperframes.mp4",
                 duration=1800, real_agent=True, session_name="hb-record"):
        self.model = model
        self.base_url = base_url
        self.output = output
        self.duration = duration
        self.real_agent = real_agent
        self.session = session_name
        self.trigger = f"/tmp/{session_name}_go"
        self.runner_log = f"/tmp/{session_name}_runner.log"

    def build_armed_session(self):
        """Create tmux session with all panes armed (waiting on trigger)."""
        tmux = lambda *args: subprocess.run(
            ["tmux", *args], capture_output=True, text=True)

        # Kill stale session
        tmux("kill-session", "-t", self.session)

        armed = lambda title, cmd: (
            f"printf '\\033]2;{title}\\033\\\\'; "
            f"tput civis; "  # hide cursor
            f"echo '╔══════════════════════════════╗'; "
            f"echo '║  ARMED: {title}'; "
            f"echo '║  Waiting for trigger...'; "
            f"echo '╚══════════════════════════════╝'; "
            f"while [ ! -f {self.trigger} ]; do sleep 0.2; done; "
            f"clear; "
            f"{cmd}"
        )

        real_flag = "--real-agent" if self.real_agent else ""
        runner_cmd = (
            f"cd ~/hermesbenchv0_1 && "
            f"python3 -m hermesbench run --all "
            f"--model {self.model} --base-url {self.base_url} "
            f"{real_flag} 2>&1 | tee {self.runner_log}"
        )

        metrics_cmd = (
            f"python3 -m hermesbench.metrics_panel "
            f"--vllm-url {self.base_url.rsplit('/', 1)[0]} "
            f"--runner-log {self.runner_log}"
        )

        agent_cmd = (
            f"while true; do "
            f"  S=$(tmux list-sessions 2>/dev/null | grep 'hb-' | head -1 | cut -d: -f1); "
            f"  if [ -n \"$S\" ]; then tmux capture-pane -t \"$S\" -p; fi; "
            f"  sleep 1; "
            f"done"
        )

        score_cmd = (
            f"while true; do "
            f"  clear; "
            f"  echo '╔══════ Scoreboard ═══════╗'; "
            f"  P=$(grep -c PASS {self.runner_log} 2>/dev/null || echo 0); "
            f"  F=$(grep -c FAIL {self.runner_log} 2>/dev/null || echo 0); "
            f"  echo \"║  PASS: $P    FAIL: $F\"; "
            f"  echo '╚════════════════════════╝'; "
            f"  sleep 2; "
            f"done"
        )

        telemetry_cmd = (
            f"while true; do "
            f"  nvidia-smi --query-gpu=utilization.gpu,temperature.gpu,power.draw "
            f"    --format=csv,noheader,nounits 2>/dev/null | "
            f"    awk -F, '{{printf \"GPU: %s%%  Temp: %s°C  Pwr: %sW\\n\", $1, $2, $3}}'; "
            f"  sleep 1; "
            f"done"
        )

        # Pane 1: Runner (top-left)
        r = tmux("new-session", "-d", "-s", self.session, "-x", "200", "-y", "56",
                  armed("Runner", runner_cmd))

        # Pane 2: Metrics (top-right)
        tmux("split-window", "-h", "-t", f"{self.session}:0", "-p", "45",
             armed("Metrics", metrics_cmd))

        # Pane 3: Agent (bottom-left)
        tmux("select-pane", "-t", f"{self.session}:0.0")
        tmux("split-window", "-v", "-t", f"{self.session}:0.0", "-p", "55",
             armed("Agent Session", agent_cmd))

        # Pane 4: Scoreboard (bottom-right)
        tmux("split-window", "-v", "-t", f"{self.session}:0.2", "-p", "55",
             armed("Scoreboard", score_cmd))

        # Pane 5: Telemetry strip (split from pane 3, full width bottom)
        tmux("select-pane", "-t", f"{self.session}:0.2")
        tmux("split-window", "-v", "-t", f"{self.session}:0.2", "-p", "20",
             armed("Telemetry", telemetry_cmd))

        # Style
        tmux("select-layout", "-t", f"{self.session}:0", "tiled")
        tmux("set-option", "-t", self.session, "pane-border-status", "top")
        tmux("set-option", "-t", self.session, "pane-border-format",
             "#[bold,fg=cyan] #{pane_index}: #[fg=yellow]#{pane_title} ")
        tmux("set-option", "-t", self.session, "status-left",
             "#[bold,fg=green] 🔴 HYPERFRAMES ")

    def start_xvfb_and_record(self, duration):
        """Launch Xvfb + xterm + ffmpeg to capture the tmux session."""
        display = ":98"
        geometry = "1920x1080x24"

        # Start Xvfb (no cursor)
        xvfb = subprocess.Popen(["Xvfb", display, "-screen", "0", geometry, "-nocursor"])

        time.sleep(2)

        # Start xterm attached to tmux
        xterm = subprocess.Popen([
            "xterm", "-display", display,
            "-geometry", "240x65+0+0",
            "-bg", "#0a0a14", "-fg", "#e0e0e8",
            "-cr", "#0a0a14", "-ms", "#0a0a14",  # cursor = background
            "-xrm", "XTerm*cursorBlink: false",
            "-fa", "Monospace", "-fs", "9",
            "-e", "tmux", "attach", "-t", self.session
        ])

        time.sleep(3)

        # Start ffmpeg capture
        out_path = str(Path(self.output).resolve())
        ffmpeg = subprocess.Popen([
            "ffmpeg", "-y",
            "-f", "x11grab",
            "-draw_mouse", "0",
            "-video_size", "1920x1080",
            "-framerate", "30",
            "-i", display,
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            out_path
        ])

        return xvfb, xterm, ffmpeg

    def run(self):
        """Full workflow: build session, wait for user, record."""
        os.makedirs(Path(self.output).parent, exist_ok=True)

        # Remove stale trigger
        if os.path.exists(self.trigger):
            os.remove(self.trigger)

        self.build_armed_session()

        print(f"""
╔══════════════════════════════════════════════╗
║  Hyperframes Session Ready                   ║
╠══════════════════════════════════════════════╣
║                                              ║
║  1. Attach to session:                       ║
║     tmux attach -t {self.session:<22s} ║
║                                              ║
║  2. Start your screen recorder               ║
║     (or this will record headlessly)          ║
║                                              ║
║  3. The recording will auto-start when        ║
║     you trigger the benchmark.                ║
║                                              ║
║  Panes:                                      ║
║    0: Runner (task progress)                 ║
║    1: Metrics (GPU/temp/power/tok/s)        ║
║    2: Agent Session (live tool calls)        ║
║    3: Scoreboard (pass/fail tally)           ║
║    4: Telemetry strip (nvidia-smi)           ║
║                                              ║
╚══════════════════════════════════════════════╝

Output: {self.output}
Duration: {self.duration}s ({self.duration/60:.0f} min)

Press ENTER to start recording + trigger benchmark...
""")
        input()

        # Start recording
        xvfb, xterm, ffmpeg = self.start_xvfb_and_record(self.duration)
        time.sleep(2)

        # Fire trigger — all panes start
        Path(self.trigger).touch()
        start = time.time()
        print(f"▶ Recording started. Trigger fired. Benchmark running...")

        # Wait for recording to complete
        try:
            ffmpeg.wait(timeout=self.duration + 30)
        except subprocess.TimeoutExpired:
            ffmpeg.terminate()

        elapsed = time.time() - start
        print(f"\n■ Recording complete ({elapsed:.0f}s)")
        print(f"  Output: {self.output}")

        # Cleanup
        for p in [xterm, xvfb]:
            try: p.terminate()
            except: pass

        # Verify output
        out = Path(self.output)
        if out.exists() and out.stat().st_size > 1_000_000:
            print(f"  Size: {out.stat().st_size / 1e6:.1f} MB ✓")
        else:
            print(f"  ⚠ Output too small ({out.stat().st_size} bytes) — recording may have failed")

        tmux_kill = subprocess.run(
            ["tmux", "kill-session", "-t", self.session],
            capture_output=True)
```

### 5.4 CLI command

```python
@main.command()
@click.option("--model", "-m", required=True)
@click.option("--base-url", required=True)
@click.option("--output", "-o", default="hyperframes.mp4")
@click.option("--duration", "-d", type=int, default=1800, help="Recording duration in seconds")
@click.option("--real-agent/--fake-agent", default=True)
@click.option("--attach/--no-attach", default=False, help="Attach to tmux instead of headless")
def record(model, base_url, output, duration, real_agent, attach):
    """Record a hyperframes video of the benchmark with live telemetry.

    Creates a 5-pane tmux session showing runner progress, GPU metrics,
    agent session, scoreboard, and telemetry strip. Records to MP4.

    \b
    Panes:
      0: Runner (task progress + pass/fail)
      1: Metrics (GPU util/temp/power, decode tok/s, cache hit, sparklines)
      2: Agent Session (live tool calls from current task)
      3: Scoreboard (pass/fail tally, category breakdown)
      4: Telemetry strip (nvidia-smi one-liner, updates every 1s)
    """
    from hermesbench.record import HyperframesRecorder
    rec = HyperframesRecorder(
        model=model, base_url=base_url, output=output,
        duration=duration, real_agent=real_agent)
    rec.run()
```

### 5.5 Headless recording script

`scripts/record_tmux.sh` — reusable wrapper for Xvfb+xterm+ffmpeg:

```bash
#!/usr/bin/env bash
set -euo pipefail
# Record a tmux session to MP4 via Xvfb + xterm + ffmpeg
# Usage: record_tmux.sh <session> <output.mp4> <duration_sec>

SESSION="${1:?Usage: $0 <tmux-session> <output.mp4> <duration_sec>}"
OUTPUT="${2:?Missing output path}"
DURATION="${3:-1800}"
DISPLAY=:98
GEOMETRY="1920x1080x24"

echo "Starting Xvfb on $DISPLAY..."
Xvfb $DISPLAY -screen 0 $GEOMETRY -nocursor &
XVFB_PID=$!
sleep 2

echo "Opening xterm attached to $SESSION..."
xterm -display $DISPLAY -geometry 240x65+0+0 \
    -bg "#0a0a14" -fg "#e0e0e8" \
    -cr "#0a0a14" -ms "#0a0a14" \
    -xrm "XTerm*cursorBlink: false" \
    -fa "Monospace" -fs 9 \
    -e "tmux attach -t $SESSION" &
XTERM_PID=$!
sleep 3

echo "Recording $DURATION seconds to $OUTPUT..."
ffmpeg -y -f x11grab -draw_mouse 0 \
    -video_size 1920x1080 -framerate 30 \
    -i $DISPLAY -t "$DURATION" \
    -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p \
    "$OUTPUT"

kill $XTERM_PID $XVFB_PID 2>/dev/null || true
echo "Done: $OUTPUT ($(du -h "$OUTPUT" | cut -f1))"
```

### 5.6 Post-processing helper

```python
@main.command(name="post-process")
@click.argument("video_path", type=click.Path(exists=True))
@click.option("--trim-start", "-s", type=int, default=5, help="Trim first N seconds")
@click.option("--trim-end", "-e", type=int, default=5, help="Trim last N seconds")
@click.option("--thumbnail", "-t", is_flag=True, help="Extract thumbnail frame")
@click.option("--highlight", "-h", type=int, help="Extract N-second highlight reel")
@click.option("--out", "-o", help="Output path (default: <name>_final.mp4)")
def post_process(video_path, trim_start, trim_end, thumbnail, highlight, out):
    """Trim, extract thumbnail, or create highlight reel from recording."""
    ...
```

---

## WORKSTREAM 6: Versioning + Release

### 5.1 pyproject.toml changes

```toml
version = "0.2.0"
description = "HermesBench — benchmark local models on real Hermes Agent tool-calling patterns"

[project.optional-dependencies]
dev = ["pre-commit>=3.7", "uv>=0.1"]
html = ["jinja2>=3.1"]  # for HTML report templates
render = ["asciinema"]  # for .cast rendering
```

### 5.2 README.md rewrite

Key changes:
- Remove "private until v0.1 release" (it's v0.2 now)
- Update all CLI examples to v0.2 syntax
- Add Quick Start with install.sh
- Add serve command
- Add real-agent instructions
- Add config file section
- Add comparison/report examples

### 5.3 Git workflow

```bash
cd ~/hermesbenchv0_1
git checkout -b v0.2

# Implement all workstreams...
# Commit per workstream:
git commit -m "feat: real hermes-agent integration (--real-agent flag)"
git commit -m "feat: install.sh auto-installer + config system"
git commit -m "feat: render, export-sft, serve, compare commands"
git commit -m "feat: scoring aggregation + per-category + HTML reports"
git commit -m "feat: run options (--results-dir, --n-runs, --resume)"
git commit -m "feat: hyperframes video capture (record command + live metrics panel)"
git commit -m "docs: update README for v0.2"
git commit -m "bump: version 0.2.0"

git push origin v0.2
# Create PR to main
# Tag: git tag v0.2.0
```

---

## EXECUTION ORDER

```
Phase 1: Foundation (1 hr)
  1. Branch v0.2
  2. config.py + hermesbench.yaml.example
  3. install.sh + Makefile update
  4. pyproject.toml version bump + deps

Phase 2: Core Commands (2 hrs)
  5. cli.py: add --results-dir, --n-runs, --resume, --real-agent
  6. hermes_invocation.py: dual mode (real + fake)
  7. runner.py: wire new options
  8. serve.py + serve command
  9. Fix stats command

Phase 3: Output Commands (1 hr)
  10. render.py + render command
  11. sft_export.py + export-sft command
  12. scoring.py aggregation
  13. report.py + HTML generation
  14. compare.py + compare command

Phase 4: Hyperframes Video (2 hrs)
  15. metrics_panel.py (live GPU/vLLM telemetry with sparklines)
  16. record.py (5-pane tmux orchestrator + Xvfb + ffmpeg)
  17. record command in cli.py
  18. post-process command (trim, thumbnail, highlight)
  19. scripts/record_tmux.sh (reusable capture wrapper)
  20. Smoke test: 30-second headless recording

Phase 5: Polish (1 hr)
  21. README.md rewrite (include record command, hyperframes section)
  22. Test: make test
  23. Test: install.sh on clean state
  24. Test: hermesbench record end-to-end
  25. PR push + tag
```

## RISK MATRIX

| Risk | Impact | Mitigation |
|------|--------|------------|
| Real hermes-agent CLI may differ from expected interface | Blocks WS1 | Test `hermes chat -q "..." --model X --yolo` manually first |
| Real agent spawn needs different stdin/stdout protocol | Blocks WS1 | Keep fake mode as default; --real-agent is opt-in |
| agg not available on most systems | Blocks render GIF | Fallback: ffmpeg from .cast (slower), or skip GIF |
| vLLM serve flags differ per quantization | Blocks WS2 | Config file lets user override; serve.py uses defaults |
| Hermes CLI version differences | Blocks WS1 | Version detection in hermes_invocation.py |
| 5-pane tmux layout breaks on small terminals | Blocks WS5 | Use 200x56 fixed geometry; Xvfb ignores real terminal size |
| Xvfb/xterm not installed | Blocks WS5 | install.sh checks and apt-installs; record.py degrades gracefully |
| ffmpeg capture produces blank frames | Blocks WS5 | Smoke test 30s recording first; verify file size > 1MB |
| Agent session pane shows nothing (no hb-* tmux sessions) | Blocks WS5 | Fallback: show runner log tail instead; pane 2 already has metrics |
