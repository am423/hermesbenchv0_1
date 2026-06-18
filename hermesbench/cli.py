"""hermesbench CLI: list, validate, run, score, render, doctor, archive, etc."""
from __future__ import annotations

import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from hermesbench import __version__
from hermesbench.types import TaskSpec

REPO = Path(__file__).resolve().parent.parent
console = Console(stderr=True)


def _discover_tasks() -> list[Path]:
    """Return all task directories (each containing task.yaml)."""
    out: list[Path] = []
    tasks_root = REPO / "tasks"
    for p in sorted(tasks_root.rglob("task.yaml")):
        if "_template" in p.parts:
            continue
        out.append(p.parent)
    return out


def _load_task(task_dir: Path) -> TaskSpec:
    return TaskSpec.from_yaml(task_dir / "task.yaml")


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """hermesbench: a benchmark for local models in the Hermes Agent harness."""


@main.command()
@click.option("--category", "-c", help="Filter by category (e.g. t03_patch_edit)")
@click.option("--difficulty", "-d", type=int, help="Filter by difficulty (1, 2, or 3)")
def list(category: str | None, difficulty: int | None) -> None:
    """List all available tasks."""
    table = Table("ID", "Name", "Difficulty", "Tags")
    for td in _discover_tasks():
        try:
            spec = _load_task(td)
        except Exception as e:
            console.print(f"[red]error loading {td}: {e}[/red]")
            continue
        if category and not spec.id.startswith(category):
            continue
        if difficulty and spec.difficulty != difficulty:
            continue
        table.add_row(spec.id, spec.name, str(spec.difficulty), ", ".join(spec.tags))
    console.print(table)


@main.command()
@click.option(
    "--path",
    "paths",
    multiple=True,
    type=str,
    help="Path to validate (can be repeated)",
)
@click.option("--lint-only", is_flag=True, help="Lint fixtures/tasks without running")
def validate(paths: tuple[str, ...], lint_only: bool) -> None:
    """Validate task.yaml files and (if not --lint-only) try to import verifiers.

    Exit 0 on success, 4 (USER_ERROR) on bad input.
    """
    targets = [Path(p) for p in paths] if paths else [REPO / "fixtures", REPO / "tasks"]
    errors: list[tuple[Path, str]] = []
    for target in targets:
        if target.is_file() and target.name == "task.yaml":
            try:
                spec = _load_task(target.parent)
                console.print(f"[green]OK[/green] {spec.id}")
            except Exception as e:
                errors.append((target, str(e)))
        elif target.is_dir():
            for td in sorted(target.rglob("task.yaml")):
                if "_template" in td.parts:
                    continue
                try:
                    spec = _load_task(td.parent)
                    console.print(f"[green]OK[/green] {spec.id}")
                except Exception as e:
                    errors.append((td, str(e)))
        else:
            errors.append((target, "not a file or directory"))
    if errors:
        for p, e in errors:
            console.print(f"[red]FAIL[/red] {p}: {e}")
        sys.exit(4)
    console.print(f"[green]All {len(targets)} target(s) valid[/green]")


@main.command()
@click.option("--model", "-m", help="Model name (from CLI or hermesbench.yaml)")
@click.option("--task", "-t", help="Single task ID to run")
@click.option("--category", "-c", help="Run all tasks in this category")
@click.option("--all", "run_all", is_flag=True, help="Run all tasks")
@click.option("--base-url", help="OpenAI-compatible base URL (or from config)")
@click.option("--dry-run", is_flag=True, help="Validate without spawning hermes")
@click.option("--real-agent", is_flag=True, help="Use real hermes-agent instead of fake")
@click.option("--results-dir", "-r", default="./results", help="Output directory")
@click.option("--n-runs", "-n", type=int, default=1, help="Run each task N times")
@click.option("--resume", "resume_dir", help="Resume from a previous run dir")
@click.option("--config", "config_path", default=None, help="Path to hermesbench.yaml")
def run(
    model: str | None,
    task: str | None,
    category: str | None,
    run_all: bool,
    base_url: str | None,
    dry_run: bool,
    real_agent: bool,
    results_dir: str,
    n_runs: int,
    resume_dir: str | None,
    config_path: str | None,
) -> None:
    """Run one or more tasks against a model."""
    from hermesbench.config import load_config
    cfg = load_config(config_path)
    model = model or cfg.get("model", {}).get("name")
    base_url = base_url or cfg.get("model", {}).get("base_url")
    if cfg.get("hermes", {}).get("real_agent", False):
        real_agent = True

    if not model:
        console.print("[red]--model required (or set model.name in hermesbench.yaml)[/red]")
        sys.exit(2)
    if not base_url and not dry_run:
        console.print("[red]--base-url required (or set model.base_url in hermesbench.yaml)[/red]")
        sys.exit(2)

    from hermesbench.runner import run_task

    targets: list[TaskSpec] = []
    if task:
        found = False
        for td in _discover_tasks():
            spec = _load_task(td)
            if spec.id == task:
                targets.append(spec)
                found = True
                break
        if not found:
            console.print(f"[red]task not found: {task}[/red]")
            sys.exit(4)
    elif category:
        for td in _discover_tasks():
            spec = _load_task(td)
            if spec.id.startswith(category + "/"):
                targets.append(spec)
        if not targets:
            console.print(f"[red]no tasks in category: {category}[/red]")
            sys.exit(4)
    elif run_all:
        for td in _discover_tasks():
            targets.append(_load_task(td))
    else:
        console.print("[red]specify --task, --category, or --all[/red]")
        sys.exit(4)

    console.print(f"running {len(targets)} task(s) against {model}")
    if real_agent:
        console.print("[cyan]using real hermes-agent[/cyan]")
    passed = 0
    for spec in targets:
        console.print(f"  -> {spec.id}...", end=" ")
        result = run_task(spec, model=model, base_url=base_url or "",
                         dry_run=dry_run, use_real_agent=real_agent)
        if result.verifier_result.status.value == "PASS":
            console.print("[green]PASS[/green]")
            passed += 1
        elif result.verifier_result.status.value == "SKIPPED":
            console.print("[yellow]SKIPPED[/yellow] (dry-run)")
        else:
            console.print(f"[red]{result.verifier_result.status.value}[/red] {result.verifier_result.reason}")
    if not dry_run:
        rate = passed / len(targets) if targets else 0
        console.print(f"\n[bold]pass rate: {passed}/{len(targets)} ({rate:.0%})[/bold]")


@main.command()
def doctor() -> None:
    """Pre-flight checks: are all deps and endpoints healthy?"""
    import importlib

    checks: list[tuple[str, bool, str]] = []
    # tmux
    checks.append(("tmux", shutil.which("tmux") is not None, "apt install tmux"))
    # bash
    checks.append(("bash", shutil.which("bash") is not None, ""))
    # pyte
    try:
        import pyte  # noqa: F401

        checks.append(("pyte", True, ""))
    except ImportError:
        checks.append(("pyte", False, "pip install pyte"))
    # pynvml
    try:
        import pynvml  # noqa: F401

        checks.append(("pynvml", True, ""))
    except ImportError:
        checks.append(("pynvml", False, "pip install pynvml"))
    # psutil
    try:
        import psutil  # noqa: F401

        checks.append(("psutil", True, ""))
    except ImportError:
        checks.append(("psutil", False, "pip install psutil"))
    # ffmpeg
    checks.append(("ffmpeg", shutil.which("ffmpeg") is not None, "apt install ffmpeg"))
    # agg
    checks.append(("agg", shutil.which("agg") is not None, "https://github.com/asciinema/agg"))
    # hermes-agent reachable
    try:
        from hermesbench.hermes_invocation import find_hermes_agent

        path = find_hermes_agent()
        checks.append(("hermes-agent", True, f"at {path}"))
    except FileNotFoundError:
        checks.append(("hermes-agent", False, "set $HERMES_AGENT_PATH or pip install"))
    # archives dir writable
    archives = Path.home() / ".hermes" / "archives"
    try:
        archives.mkdir(parents=True, exist_ok=True)
        test = archives / ".doctor_test"
        test.write_text("ok")
        test.unlink()
        checks.append(("archives dir", True, f"at {archives}"))
    except Exception as e:
        checks.append(("archives dir", False, str(e)))

    table = Table("Check", "Status", "Remediation")
    all_ok = True
    for name, ok, fix in checks:
        status = "[green]✓[/green]" if ok else "[red]✗[/red]"
        if not ok:
            all_ok = False
        table.add_row(name, status, fix)
    console.print(table)
    if not all_ok:
        sys.exit(4)


@main.command()
@click.option("--path", "-p", "run_paths", multiple=True, required=True, help="Run dir(s) to score")
@click.option("--by-category", is_flag=True, help="Break down by task category")
@click.option("--html", "-h", help="Generate HTML report at this path")
def score(run_paths: tuple[str, ...], by_category: bool, html: str | None) -> None:
    """Score and summarize results across one or more runs."""
    from hermesbench.scoring import aggregate_results, category_breakdown

    all_results = aggregate_results(list(run_paths))
    total = len(all_results)
    passed = sum(1 for r in all_results if r.get("status") == "PASS")
    rate = passed / total * 100 if total else 0

    console.print(f"\nOverall: {passed}/{total} ({rate:.1f}%)")

    if by_category:
        cats = category_breakdown(all_results)
        for cat, (p, t) in sorted(cats.items()):
            console.print(f"  {cat:<30} {p}/{t} ({p/t*100:.0f}%)")

    if html:
        from hermesbench.report import generate_html_report
        generate_html_report(all_results, html)
        console.print(f"HTML report: {html}")


@main.command()
@click.option("--path", "-p", required=True, help="Run directory")
def stats(path: str) -> None:
    """Show hardware stats summary for a run."""
    from hermesbench.scoring import compute_hardware_summary
    summary = compute_hardware_summary(path)
    console.print(f"Run: {path}")
    for key, val in summary.items():
        if isinstance(val, float):
            console.print(f"  {key}: {val:.2f}")
        else:
            console.print(f"  {key}: {val}")


@main.command()
@click.option("--model", "-m", required=True, help="Model path or HF ID")
@click.option("--port", "-p", default=8999, help="Port for vLLM server")
@click.option("--quantization", default=None, help="Quantization method")
@click.option("--served-name", default=None, help="Served model name")
@click.option("--config", "-c", default=None, help="Path to hermesbench.yaml")
def serve(model: str, port: int, quantization: str | None,
          served_name: str | None, config: str | None) -> None:
    """Launch a vLLM server with benchmark-correct flags."""
    from hermesbench.serve import launch_vllm
    launch_vllm(model, port, quantization, config, served_name)


@main.command()
@click.argument("cast_path", type=click.Path(exists=True))
@click.option("--format", "-f", "fmt", type=click.Choice(["gif", "mp4"]), default="gif")
@click.option("--out", "-o", help="Output file path")
def render(cast_path: str, fmt: str, out: str | None) -> None:
    """Render an asciinema .cast file to .gif or .mp4."""
    from hermesbench.render import render_cast
    try:
        result = render_cast(cast_path, fmt, out)
        console.print(f"Rendered: {result}")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@main.command(name="export-sft")
@click.option("--path", "-p", "run_paths", multiple=True, required=True, help="Run directory")
@click.option("--out", "-o", required=True, help="Output .jsonl file")
def export_sft(run_paths: tuple[str, ...], out: str) -> None:
    """Export conversation traces to SFT-ready JSONL with loss masks."""
    from hermesbench.sft_export import export_sft as do_export
    count = do_export(list(run_paths), out)
    console.print(f"Exported {count} examples to {out}")


@main.command()
@click.option("--path", "-p", "run_paths", multiple=True, required=True,
              help="Run directories to compare (at least 2)")
@click.option("--html", "-o", help="Output HTML comparison report")
def compare(run_paths: tuple[str, ...], html: str | None) -> None:
    """Compare results across multiple model runs."""
    from hermesbench.compare import compare_runs
    from hermesbench.scoring import aggregate_results

    results = {}
    for p in run_paths:
        results[p] = aggregate_results([p])

    if len(results) < 2:
        console.print("[yellow]Warning: need at least 2 runs for comparison[/yellow]")

    table = compare_runs(results)
    console.print(table)

    if html:
        from hermesbench.report import generate_comparison_html
        generate_comparison_html(results, html)
        console.print(f"HTML report: {html}")


@main.command()
@click.option("--model", "-m", required=True, help="Model name")
@click.option("--base-url", required=True, help="Model base URL")
@click.option("--output", "-o", default="videos/hyperframes.mp4", help="Output video path")
@click.option("--duration", "-d", type=int, default=1800, help="Recording duration (seconds)")
@click.option("--real-agent/--fake-agent", default=True, help="Use real hermes-agent")
@click.option("--attach/--headless", default=False,
              help="--attach: manual recording. --headless: auto-record via Xvfb+ffmpeg")
def record(model: str, base_url: str, output: str, duration: int,
           real_agent: bool, attach: bool) -> None:
    """Record a hyperframes video of the benchmark with live telemetry."""
    from hermesbench.record import HyperframesRecorder
    rec = HyperframesRecorder(
        model=model, base_url=base_url, output=output,
        duration=duration, real_agent=real_agent, attach_mode=attach)
    rec.run()


@main.command(name="post-process")
@click.argument("video_path", type=click.Path(exists=True))
@click.option("--trim-start", "-s", type=int, default=0, help="Trim first N seconds")
@click.option("--trim-end", "-e", type=int, default=0, help="Trim last N seconds")
@click.option("--thumbnail", "-t", is_flag=True, help="Extract thumbnail at 25% mark")
@click.option("--out", "-o", help="Output path")
def post_process(video_path: str, trim_start: int, trim_end: int,
                 thumbnail: bool, out: str | None) -> None:
    """Trim video and/or extract thumbnail frame."""
    import subprocess
    import json as _json
    vp = Path(video_path)
    base_out = out or str(vp.with_stem(vp.stem + "_final"))

    if trim_start or trim_end:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", str(vp)],
            capture_output=True, text=True)
        duration = float(_json.loads(result.stdout)["format"]["duration"])
        start = trim_start
        end = duration - trim_end
        subprocess.run([
            "ffmpeg", "-y", "-ss", str(start), "-to", str(end),
            "-i", str(vp), "-c", "copy", base_out + ".mp4"], check=True)
        console.print(f"Trimmed: {base_out}.mp4 ({end - start:.0f}s)")

    if thumbnail:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", str(vp)],
            capture_output=True, text=True)
        duration = float(_json.loads(result.stdout)["format"]["duration"])
        thumb_time = duration * 0.25
        thumb_path = (out or str(vp.with_stem(vp.stem + "_thumb"))) + ".png"
        subprocess.run([
            "ffmpeg", "-y", "-ss", str(thumb_time), "-i", str(vp),
            "-vframes", "1", "-q:v", "2", thumb_path], check=True)
        console.print(f"Thumbnail: {thumb_path}")


if __name__ == "__main__":
    main()
