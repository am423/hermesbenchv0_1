# Benchmark presets

JSON files here capture prior run summaries and suggested re-run scopes.

## `weak_categories_grok.json`

From run `grok_composer_real_20260617_130400` with `grok-composer-2.5-fast` (31/48 on core categories in that snapshot). Use `rerun_category_flags` for focused improvement runs:

| Category | CLI flag |
|----------|----------|
| `t03_patch_edit` | `--category t03_patch_edit` |
| `t08_execute_code` | `--category t08_execute_code` |
| `t11_error_recovery` | `--category t11_error_recovery` |

### Example: rerun one weak category

```bash
hermesbench run --use-hermes-config \
  --model grok-composer-2.5-fast \
  --category t03_patch_edit \
  --toolsets all
```

### Example: resume a full run and only execute remaining tasks

```bash
hermesbench run --use-hermes-config \
  --model grok-composer-2.5-fast \
  --resume grok_composer_real_20260617_130400 \
  --all \
  --toolsets all
```

### Example: all three weak categories (separate runs)

```bash
for cat in t03_patch_edit t08_execute_code t11_error_recovery; do
  hermesbench run --use-hermes-config \
    --model grok-composer-2.5-fast \
    --category "$cat" \
    --toolsets all \
    --run-id "grok_rerun_${cat}_$(date +%Y%m%d)"
done
```

See `docs/RUN_LAYOUT.md` for artifact paths and resume semantics.