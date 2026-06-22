# Diagnosing zero-score categories

HermesBench failures are not automatically model failures. Before retraining or changing prompts, inspect the trace and classify the failure.

## Fast checklist

1. Run `python3 -m hermesbench fixture-integrity` before scoring patch/search/write categories.
2. Locate the task trace under `traces/<run_id>/<category>/<task>/trace.jsonl` or, for custom output roots, `OUT/traces/<run_id>/<category>/<task>/trace.jsonl`.
3. Confirm the model saw the expected tool in the system/tool schema.
4. Confirm the model called the tool the verifier expects.
5. Confirm file mutations happened inside the task worktree, not an absolute host path.
6. Read `verifier_result.json`; the canonical pass field is `status: "PASS"`, not `passed: true`.

## Common failure classes

| Symptom | Likely cause | Fix |
|---|---|---|
| Model says `search_files` is unavailable | `search_files` mapped to the wrong Hermes toolset | Ensure `search_files -> file` in `TOOLSET_MAP`. |
| Write task says file not created, but trace shows write succeeded | Model wrote an absolute host path | Train/evaluate with relative paths and keep `cwd` at the worktree. |
| Patch task refuses because code is already fixed | Polluted fixture | Reset tracked fixture files or intentionally commit fixture changes. |
| Empty or plain-text trace | agent crash or session export failed | Inspect `meta.json`, stderr, and Hermes session export. |
| All API model tasks fail 401 in fake mode | endpoint smoke test missing auth | Ensure `OPENAI_API_KEY` is exported or use real-agent mode. |

## Output-root behavior

Default:

```text
results/<run_id>/<task_id>/verifier_result.json
traces/<run_id>/<task_id>/trace.jsonl
```

Custom:

```bash
python3 -m hermesbench run --category t04_search_grep \
  --model MODEL --base-url URL --real-agent --results-dir /tmp/hb-out
```

writes:

```text
/tmp/hb-out/<run_id>/<task_id>/verifier_result.json
/tmp/hb-out/traces/<run_id>/<task_id>/trace.jsonl
```

Use `python3 -m hermesbench score -p /tmp/hb-out --by-category` to aggregate.
