# Run layout and resume

HermesBench writes artifacts under the repository root (or `--repo-root`).

## Directory layout (real engine, default)

| Path | Contents |
|------|----------|
| `results/<run_id>/summary.json` | Run metadata, pass/fail counts, per-task rows |
| `results/<run_id>/<task_id_underscored>.json` | Single-task snapshot (same fields as one `tasks[]` entry) |
| `traces/<run_id>/<task_id>/run_agent.log` | stdout/stderr from `run_agent.py` |
| `traces/<run_id>/<task_id>/trace.jsonl` | Converted conversation trace |
| `traces/<run_id>/<task_id>/verifier_result.json` | Verifier output |

Task IDs use slashes in paths under `traces/` (e.g. `t03_patch_edit/t01_basic`). Under `results/`, slashes become underscores in per-task JSON filenames.

## Resume — real engine (`--engine real`)

When continuing a partial run, reuse the same `run_id` so new results merge into the existing tree.

**Skip rule:** tasks whose prior row in `summary.json` has `status` of `PASS` or `FAIL` are not executed again. Other statuses (if any) are re-run. The final `summary.json` lists all selected tasks in selection order, merging skipped rows with freshly executed ones.

**CLI patterns:**

```bash
# Shorthand: --resume sets run_id and enables skip
hermesbench run --resume my_run_20260618 --all --use-hermes-config --model grok-composer-2.5-fast

# Explicit run id + flag
hermesbench run --run-id my_run_20260618 --resume-skipped --category t03_patch_edit \
  --use-hermes-config --model grok-composer-2.5-fast

# Module entrypoint
python -m hermesbench.run_real --run-id my_run --resume --tasks t03_patch_edit/t01_basic
```

Dry-run with resume shows how many tasks would be skipped vs executed.

## Resume — legacy engine (`--engine legacy`)

Legacy runs use a different layout under `--results-dir` (tmux runner, `meta.json`, per-task run folders). The `--resume <dir>` option is passed through for compatibility; behavior matches the legacy runner in `hermesbench.runner` (not `summary.json` merge).

## Scoring and reports

```bash
hermesbench score results/<run_id>/
hermesbench score traces/<run_id>/<task_id>/
hermesbench report --run-id <run_id>
```

`hermesbench score` accepts a run directory (`results/<run_id>/` or legacy run dir) or a single task trace directory containing `verifier_result.json`.