# HermesBench — AGENTS.md

This file is for **coding agents** (Hermes, Cursor, Claude Code, etc.) working in this repository. Follow it for install, benchmark runs, and safe edits.

## What this repo is

**HermesBench v0.1** benchmarks **models inside real [Hermes Agent](https://github.com/NousResearch/hermes-agent)** — tool use (terminal, patch, search, execute_code, web, memory, …), not chat-only QA.

- **48 tasks** under `tasks/**/task.yaml` (11 categories, difficulties 1–3)
- Each task: isolated git worktree, prompt, verifier under `tasks/.../verifier.py`
- **Official benchmark command:** `hermesbench run` → spawns `run_agent.py` from the Hermes Agent checkout

There is **no** fake-agent benchmark path in the CLI anymore. `tests/support/fake_hermes.py` exists only for optional pipeline tests.

## Repository layout (agent-relevant)

```
hermesbench/
  cli.py              # CLI entry (run, validate, doctor, setup, report, …)
  run_real.py         # Benchmark engine (run_agent.py per task)
  preflight.py        # doctor checks + pip --install
  hermes_invocation.py # find_hermes_agent(), hermes_python()
  runner.py           # Legacy tmux/fake pipeline — not used by `hermesbench run`
tasks/                # Task definitions + verifiers
results/<run_id>/     # summary.json + per-task JSON
traces/<run_id>/      # logs, trace.jsonl, worktrees
scripts/bootstrap.sh  # Clone-and-run venv setup
docs/GETTING_STARTED.md
docs/PROVIDERS.md
AGENTS.md             # This file
```

## Prerequisites (check before benchmarking)

| Requirement | Why |
|-------------|-----|
| Python **3.11+** | Package + tests |
| **Hermes Agent** checkout | `run_agent.py`, toolsets, providers |
| Hermes **`.venv`** with `pip install -e .` | `fire`, `python-dotenv`, agent deps |
| **`~/.hermes/config.yaml`** (or `OPENAI_*`) | Model provider / API |
| **tmux**, **bash** | Hermes terminal backend in benchmarks |
| **git** | Worktrees per task |

Optional: **ffmpeg**, **agg** (casts), **Node 18+** (HyperFrames video via `hermesbench report --render-video`).

## Install (clone → runnable)

Run from repo root:

```bash
./scripts/bootstrap.sh
source .venv/bin/activate
hermesbench doctor --install
hermesbench setup --hermes --check-only
hermesbench validate
```

If Hermes Agent is missing:

```bash
git clone https://github.com/NousResearch/hermes-agent ~/.hermes/hermes-agent
cd ~/.hermes/hermes-agent && python3 -m venv .venv && .venv/bin/pip install -e .
```

Set provider in `~/.hermes/config.yaml`. For xAI OAuth / config-driven models, always use **`--use-hermes-config`** on runs (see below).

Override checkout path: `export HERMES_AGENT_PATH=/path/to/hermes-agent`

## Benchmark commands (only entrance: `hermesbench run`)

### Smoke (one task)

```bash
hermesbench run --use-hermes-config \
  --model YOUR_MODEL_ID \
  --task t01_terminal_smoke/t01_echo \
  --toolsets all
```

### Full suite (48 tasks)

```bash
hermesbench run --use-hermes-config \
  --model YOUR_MODEL_ID \
  --all \
  --toolsets all \
  --run-id my_run_$(date +%Y%m%d)
```

### Category

```bash
hermesbench run --use-hermes-config --model YOUR_MODEL_ID \
  --category t03_patch_edit --toolsets all
```

### OpenAI-compatible env (no Hermes config file)

Omit `--use-hermes-config` and set:

```bash
export OPENAI_API_KEY=...
export OPENAI_BASE_URL=http://127.0.0.1:8080/v1   # optional override
hermesbench run --model local-model --all --base-url "$OPENAI_BASE_URL"
```

### Dry-run (task selection only)

```bash
hermesbench run --dry-run --all --model x
```

Prints selected tasks; does not call the API or Hermes.

### After a run

```bash
hermesbench report --run-id <run_id>
# optional video:
hermesbench report --run-id <run_id> --render-video
```

Artifacts:

- `results/<run_id>/summary.json` — pass/fail, pass_rate, per-task reasons
- `results/<run_id>/REPORT.md` — human summary (via `report`)
- `traces/<run_id>/<task_id>/` — `run_agent.log`, `trace.jsonl`, `verifier_result.json`

## CLI reference (agents)

| Command | Purpose |
|---------|---------|
| `hermesbench setup` | `.venv` + editable install |
| `hermesbench doctor [--install] [--profile run]` | Environment + pip fixes |
| `hermesbench validate` | Lint all `task.yaml` + verifiers |
| `hermesbench list` | List tasks |
| **`hermesbench run`** | **Real benchmark** (Hermes `run_agent.py`) |
| `hermesbench run-real` | Deprecated alias for `run` |
| `hermesbench report --run-id ID` | REPORT + timeline + HF index |
| `hermesbench score --path …` | Re-score existing trace dirs |

## Critical flags for `run`

- **`--use-hermes-config`** — Use `~/.hermes/config.yaml` provider (xai-oauth, etc.). **Required** for OAuth models; avoids wrong `OPENAI_BASE_URL` overrides.
- **`--toolsets all`** — Full tool surface (matches published 48-task runs). Narrow only for debugging.
- **`--enabled_toolsets`** is passed internally as a single Fire arg: `--enabled_toolsets=all`.
- **`--hermes-agent-path`** — Override Hermes checkout.
- **`--timeout-overhead`** — Seconds added to each task’s `timeout_seconds` (default 30).

Hermes is executed with **`hermes_python(hermes_path)`** — prefer `hermes-agent/.venv/bin/python`, not system `python3`.

## Adding or changing tasks

1. Copy `tasks/_template/` pattern: `task.yaml`, `verifier.py`, optional `fixture/`.
2. `task.yaml` must define: `id`, `prompt`, `timeout_seconds`, `max_turns`, `difficulty`, `verifier`, `hermes_plugins` (if any).
3. Verifier returns `VerifierResult` with `PASS` / `FAIL` / etc. — see `hermesbench/types.py`.
4. Run `hermesbench validate` before committing.
5. Lint tests: `pytest tests/test_lint_verifiers.py tests/test_lint_fixtures.py -v`

Do **not** weaken verifiers to make a model pass; fix the model or document task difficulty.

## Testing (agents modifying code)

```bash
pip install -e ".[dev]"
pytest tests/ -m "not integration" -v
ruff check hermesbench tests
```

Exit codes: **4** = user error (bad task id, missing args). Benchmark partial fail → exit **1** if any task failed.

## Common failures (troubleshooting)

| Symptom | Fix |
|---------|-----|
| `No module named 'fire'` / `dotenv` | Use Hermes `.venv`: `hermesbench doctor --profile run` |
| OAuth / wrong provider | Add `--use-hermes-config` |
| `Could not find hermes-agent` | Clone + `HERMES_AGENT_PATH` |
| All tasks FAIL, empty trajectory | Model name wrong or API errors — check `traces/.../run_agent.log` |
| `Specify --task or --all` | CLI requires explicit scope |

## What agents should NOT do

- Do not reintroduce `fake_hermes` as the default benchmark path.
- Do not commit API keys, `config.yaml` secrets, or user `~/.hermes` contents.
- Do not compare to other models in user deliverables unless asked (standalone runs).
- Do not run full `--all` in CI without credentials (use `validate` + unit tests).

## Maintainer notes

- Never name CLI callbacks `run` or `list` — they shadow Click/builtins (`Group.run`, `list()`). Use `@main.command("list")` + `list_tasks_cmd`, etc.

## Version

Package version: `hermesbench/__init__.py` → `__version__`. Bump on CLI-breaking changes.

## Links

- Human onboarding: `docs/GETTING_STARTED.md`
- Providers: `docs/PROVIDERS.md`
- Hermes Agent docs: https://hermes-agent.nousresearch.com/docs