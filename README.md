# hermesbench v0.1

A benchmark for **local models running inside the Hermes Agent
harness**. Captures full conversation traces (every tool call +
result + reasoning + token IDs), asciinema recordings, and 5 Hz
hardware telemetry. Designed to be the ground truth for "how good
is this model at *using* hermes-agent?" — not just at generating text.

> **Repo:** `github.com/am423/hermesbenchv0_1` (private until v0.1 release)
> **Plan:** see [`project.md`](./project.md) (1,813 lines, 11 sections, 75 answered design questions)
> **Rubric:** see [`rubric.md`](./rubric.md) (the self-grade)

## What it does

- **43 tasks across 11 categories** — terminal smoke, file read,
  patch, search, write, process, todo, execute_code, web_lookup,
  memory, error_recovery
- **Runs the real `AIAgent` from `~/.hermes/hermes-agent/`** in a
  subprocess with a custom `tmux_isolated` environment backend
- **Captures three artifacts per task run:**
  - `trace.jsonl` — every system/user/assistant/tool message with
    token IDs and reasoning content (loss-masked SFT-ready)
  - `trace.cast` — asciinema v2 recording of the model's terminal
    session (X-shareable, replayable)
  - `stats.jsonl` — 5 Hz hardware telemetry (CPU, GPU, RAM, NVMe,
    host power, model process tree) with thermal warnings
- **Deterministic verifiers** for every task (stdlib-only, no
  LLM-as-judge, no flakiness from network calls)
- **6 metric groups + 9 hardware metrics** in the per-model
  summary: pass rate, tool efficiency, token efficiency, wall clock,
  recovery rate, format compliance, GPU power/temp, joules-per-token,
  thermal AUC, throttle seconds

## Quick start (5 minutes)

```bash
# 1. Install (editable, with all deps)
make install

# 2. Verify environment
make doctor

# 3. Run a single task against a local model server
python3 -m hermesbench run \
    --task t01_terminal_smoke/t01_echo \
    --model qwen2.5-coder-7b-instruct-q4_k_m \
    --base-url http://127.0.0.1:8080/v1

# 4. Run all 43 tasks
python3 -m hermesbench run --all \
    --model qwen2.5-coder-7b-instruct-q4_k_m \
    --base-url http://127.0.0.1:8080/v1

# 5. Render a task's cast to an X-ready GIF
python3 -m hermesbench render \
    traces/<run_id>/t01_terminal_smoke/t01_echo/trace.cast \
    --format gif --out t01.gif
```

## CLI

| Command | What it does |
|---|---|
| `hermesbench list` | List all 43 tasks |
| `hermesbench list --difficulty 2` | Filter by difficulty |
| `hermesbench validate` | Lint all task.yaml + verifier files |
| `hermesbench run --task <id>` | Run one task |
| `hermesbench run --all` | Run all 43 tasks |
| `hermesbench run --all --dry-run` | Validate without spawning hermes (Q72) |
| `hermesbench run --resume <run_id>` | Resume a crashed run (Q24) |
| `hermesbench run --n-runs 3` | Run each task 3× for variance (Q34) |
| `hermesbench doctor` | Pre-flight checks (Q70) |
| `hermesbench score results/<run>/` | Re-score from existing results |
| `hermesbench render <cast>` | `.cast` → `.gif`/`.mp4` with stats overlay (Q3.1a) |
| `hermesbench render --examples` | Show 5 common render invocations (Q71) |
| `hermesbench export-sft <runs>` | Traces → SFT jsonl with loss masks (Q45-Q47) |

## Architecture (30-second version)

```
task.yaml + fixtures/
       │
       ▼
  runner.py ────► statsd (subprocess, niced, pinned core)
       │                │
       │                ▼
       │         .stats.jsonl  (5 Hz telemetry)
       │
       ├──► hermes-agent (subprocess, --print-mode jsonl, --line-buffered)
       │         │
       │         │ TERMINAL_ENV=tmux_isolated
       │         ▼
       │    tmux session ──► .cast (asciinema v2, via pipe-pane)
       │    (worktree, isolated $HOME, unshare --net, ulimit)
       │         │
       │         └─► read_file, patch, search_files, terminal, …
       │
       ├──► .trace.jsonl  (system/user/assistant/tool + token IDs + reasoning)
       │
       ▼
  scoring.py ──► results/<run_id>/<task_id>/
       │
       ├──► pass_rate, J/tok, thermal warnings, hardware table
       ├──► export-sft ──► sft_dataset.jsonl  (with loss masks)
       └──► render ──► .gif / .mp4  (with --overlay-stats HUD)
```

See [`project.md` §3](./project.md) for the full design rationale.

## Layout

```
hermesbenchv0_1/
├── README.md                 # this file
├── project.md                # the design plan (1,813 lines)
├── rubric.md                 # the self-grade (95/100)
├── Makefile                  # demo / doctor / test / lint / install
├── pyproject.toml            # Python 3.11+, ruff, mypy strict
├── requirements.lock         # Q75: pinned versions
├── .pre-commit-config.yaml
├── .github/workflows/ci.yml
├── hermesbench/              # the package
│   ├── types.py              # TaskSpec, VerifierResult, HardwareMetrics
│   ├── backend/              # base, registry, tmux_isolated, recorder, worktree
│   ├── statsd/               # 5 Hz telemetry collector
│   ├── trace.py              # Q52 trace reader/normalizer
│   ├── scoring.py            # metrics, thermal compare, J/tok
│   ├── hermes_invocation.py  # Q22 path, Q50 SHA, Q57 smoke
│   ├── runner.py             # full task lifecycle
│   └── cli.py                # click + rich CLI
├── tasks/                    # 43 tasks in 11 categories
│   ├── _template/            # canonical task shape
│   ├── t01_terminal_smoke/   # 5 tasks
│   ├── t02_file_read/        # 6 tasks (incl. Q61 parallel)
│   ├── t03_patch_edit/       # 5 tasks
│   ├── t04_search_grep/      # 5 tasks
│   ├── t05_write_new/        # 5 tasks
│   ├── t06_process_mgmt/     # 5 tasks
│   ├── t07_todo_plan/        # 3 tasks
│   ├── t08_execute_code/     # 5 tasks
│   ├── t09_web_lookup/       # 3 tasks (mocked)
│   ├── t10_memory_facts/     # 3 tasks
│   └── t11_error_recovery/   # 3 tasks (Q58)
├── fixtures/                 # task input data (small_repo/, broken_code/, …)
├── scripts/
│   ├── generate_tasks.py     # idempotent task generator (Q28)
│   └── fake_model_server.py  # for end-to-end testing
├── tests/                    # 47/47 passing
└── docs/
    ├── trace_format_reconciliation.md  # Q52
    ├── adding_backends.md               # Q9.3
    └── glossary.md                      # Q9.4
```

## Tests

```bash
make test         # 47 passed, 1 deselected
```

- `test_smoke.py` — package import, pytest collect
- `test_recorder.py` — asciinema v2 roundtrip (unit + integration)
- `test_statsd.py` — 5 Hz samples for 2s, schema verification
- `test_statsd_pinning.py` — priority lowering + core detection
- `test_statsd_sources.py` — per-source shape validation
- `test_scoring.py` — hardware metrics, J/tok, thermal compare
- `test_cli.py` — every subcommand + exit codes
- `test_verifier_contract.py` — every verifier returns VerifierResult-like
- `test_trace.py` — Q52 reconciliation
- `test_lint_verifiers.py` — AST walk, stdlib allowlist
- `test_lint_fixtures.py` — injection pattern scanner
- `test_lint_fixture_sizes.py` — 100 KB cap

## Adding a new task

```bash
cp -r tasks/_template tasks/t12_my_category/t01_my_task/
$EDITOR tasks/t12_my_category/t01_my_task/task.yaml
# ... author verifier.py ...
python3 -m hermesbench validate tasks/t12_my_category/t01_my_task/
```

See [`tasks/_template/`](./tasks/_template/) for the full schema and
[`docs/glossary.md`](./docs/glossary.md) for terminology.

## Adding a new environment backend

See [`docs/adding_backends.md`](./docs/adding_backends.md). In short:
subclass `BaseHermesBenchEnvironment`, register with
`@register_backend("name")`, import from
`hermesbench/backend/__init__.py`.

## License

MIT.
