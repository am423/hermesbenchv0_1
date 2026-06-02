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
@click.option("--model", "-m", required=True, help="Model name (e.g. qwen2.5-coder-7b)")
@click.option("--task", "-t", help="Single task ID to run")
@click.option("--category", "-c", help="Run all tasks in this category")
@click.option("--all", "run_all", is_flag=True, help="Run all tasks")
@click.option("--base-url", required=True, help="OpenAI-compatible base URL")
@click.option("--dry-run", is_flag=True, help="Validate without spawning hermes")
def run(
    model: str,
    task: str | None,
    category: str | None,
    run_all: bool,
    base_url: str,
    dry_run: bool,
) -> None:
    """Run one or more tasks against a model."""
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
    passed = 0
    for spec in targets:
        console.print(f"  -> {spec.id}...", end=" ")
        result = run_task(spec, model=model, base_url=base_url, dry_run=dry_run)
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
@click.option(
    "--path",
    "paths",
    multiple=True,
    type=str,
    required=True,
    help="Path to score (can be repeated)",
)
def score(paths: tuple[str, ...]) -> None:
    """Re-score existing results."""
    from hermesbench.scoring import score_run

    targets: list[Path] = [Path(p) for p in paths]
    for p in targets:
        if not p.exists():
            console.print(f"[red]path does not exist: {p}[/red]")
            continue
        if not p.is_dir():
            console.print(f"[red]not a directory: {p}[/red]")
            continue
        # Detect whether `p` is a single run-dir or a single task-dir.
        # A run-dir has subdirs each containing verifier_result.json.
        # A task-dir contains verifier_result.json itself.
        is_task_dir = (p / "verifier_result.json").exists()
        if is_task_dir:
            from hermesbench.scoring import score_run

            parent = p.parent
            summary = score_run(parent, parent)
            console.print(
                f"[bold]{p.name}[/bold] pass_rate={summary['pass_rate']:.0%} "
                f"({len(summary['tasks'])} tasks, "
                f"{len(summary['thermal_warnings'])} thermal warnings)"
            )
            for w in summary["thermal_warnings"]:
                console.print(f"  [yellow]⚠[/yellow] {w['task']}: {w['warning']}")
            continue
        # Otherwise treat as a run-dir
        from hermesbench.scoring import score_run

        summary = score_run(p, p)
        console.print(
            f"[bold]{p.name}[/bold] pass_rate={summary['pass_rate']:.0%} "
            f"({len(summary['tasks'])} tasks, "
            f"{len(summary['thermal_warnings'])} thermal warnings)"
        )
        for w in summary["thermal_warnings"]:
            console.print(f"  [yellow]⚠[/yellow] {w['task']}: {w['warning']}")


@main.command()
def stats() -> None:
    """Show hardware stats summary for a run (TBD: argparse path)."""
    console.print("use: hermesbench stats <path-to-run-dir>")


if __name__ == "__main__":
    main()
