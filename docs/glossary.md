# Glossary

Common terms used throughout the project.

**AIAgent** — The main agent class in hermes-agent
(`hermes_agent.run_agent.AIAgent`). v0.1 of hermesbench spawns this
in a subprocess per task, with our custom `tmux_isolated` backend.

**base_url** — The OpenAI-compatible HTTP endpoint where hermesbench
sends `chat.completions` requests. Typically a local llama.cpp /
vLLM / ollama server, e.g. `http://127.0.0.1:8080/v1`.

**cast** — An asciinema v2 recording file (`.cast`). Produced by
`hermesbench/backend/recorder.py` via `tmux pipe-pane`. Replayable
with `asciinema play`.

**BaseEnvironment** — Abstract class in hermes-agent
(`tools/environments/base.py`) that backends like `local`, `docker`,
`ssh` implement. v0.1 of hermesbench uses a hermesbench-internal
ABC (`hermesbench/backend/base.py`) because hermes-agent doesn't
yet have plugin discovery for backends (Q40).

**build_dependencies** — Build-time tools required only for
GIF/MP4 rendering: `agg` (asciinema gif generator), `ffmpeg`
(MP4 transcoding). Not required to run benchmarks, only to
produce X-shareable artifacts.

**difficulty** — Per-task integer (1=easy, 2=medium, 3=hard) used
to compute `pass_rate_by_difficulty` in scoring. Models in different
size tiers should show monotonic improvement on difficulty-1 and
flat-or-declining on difficulty-3; otherwise the suite is
miscalibrated and the v0.1 gate fails.

**fixture** — Deterministic input data committed to `fixtures/`
that a task works on. Each `task.yaml` declares which fixtures are
copied into the per-task worktree. 100 KB size cap enforced by
`tests/lint_fixture_sizes.py` (Q3).

**gen_joules_per_output_token** — Honest model efficiency: the
energy used during the assistant's *generation windows* (between
user message and next tool call) divided by total output tokens.
Complement to `wall_joules_per_output_token` which includes tool-call
idle time (Q44).

**hermes_plugins** — TaskSpec field listing which hermes plugins
the model is allowed to use (default `[]` = no plugins). Runner
injects `DISABLED_TOOLSETS` for everything not in this list (Q54).
Prevents cross-run confounds from inconsistent plugin loading.

**isolated_network** — Per-task bool. When false, the tmux session
runs under `unshare --net` so the model cannot reach the internet
(Q8). Graceful fallback when unshare is missing (no crash, just a
warning).

**J/tok** — Joules per output token. See `gen_joules_per_output_token`.

**JOU** — Just Operating Unit. A unit of work. (We don't actually
use this term; it's listed here to make grep easier.)

**lance** — A unit of work. (We don't actually use this term either.
Sorry.)

**lifecycle** — The per-task sequence: `setup_worktree` →
`backend.init_session` → `statsd.Popen` → `hermes.Popen` → verifier
→ `backend.cleanup` → `statsd.terminate`. See
`hermesbench/runner.py:run_task`.

**model_endpoint** — TaskSpec field describing the OpenAI-compatible
contract the endpoint must support. Runner smoke-tests the endpoint
before each task (Q57); exit 2 if the contract is violated.

**N_runs** — Number of times to run each task. Default 1, opt-in 3 via
`--n-runs 3`. N=3 mode increments `seed` by `run_index` so the
3 runs are independent (Q34).

**parallel_tool_call_rate** — Q61 metric. For tasks that benefit
from parallelism, count tool-call *turns* (not calls): a model
that emits 3 calls in one turn scores `parallel_rate = 2/3`.

**Q-number** — e.g. "Q44" or "G2.1" in `project.md` / `rubric.md`.
Q-numbers are decided design questions; G-numbers are gaps
identified in the rubric. The full lists live in `project.md`
§10 and `rubric.md` round-3 closure table.

**recovery_rate** — Q58 metric. Per-task: did the model recover
within 2 turns after a `success: false` envelope? Top-line
indicator of tool-using capability.

**run_id** — `<model_slug>_<YYYYMMDD-HHMMSS>_<8char-uuid>`. Join
key across all artifacts (trace.jsonl, cast, stats.jsonl,
verifier_result.json, meta.json). See Q21.

**SamplingConfig** — TaskSpec block injected into hermes-agent's
`gen_kwargs` to ensure deterministic sampling (Q43). Default:
`temperature: 0.0, top_p: 1.0, top_k: -1, seed: 42`.

**stats.jsonl** — 5 Hz telemetry from `hermesbench.statsd`. 7
metric groups: CPU, GPU(s), RAM, NVMe, host_power (if available),
model_process, wall clock. Sample schema in `project.md` §3.1b.

**task.yaml** — Per-task config. Full schema in `project.md` Q20.

**tmux_isolated** — Default v0.1 backend. One tmux session per
task, persistent worktree at `traces/<run_id>/<task_id>/worktree/`,
isolated `$HOME`, per-task `ulimit`, optional `unshare --net`.
~310 LOC in `hermesbench/backend/tmux_isolated.py`.

**trace.jsonl** — The full conversation in hermes-agent wire
format. One line per message (system, user, assistant, tool).
Schema reconciled with `state.db` in
`docs/trace_format_reconciliation.md` (Q52).

**VerifierResult** — Dataclass every verifier returns.
`status: Literal["PASS", "FAIL", "SKIPPED", "BUDGET_EXCEEDED", "VERIFIER_ERROR"]`,
`score: float` (0-1), `reason: str`, `details: dict`. See Q35.
