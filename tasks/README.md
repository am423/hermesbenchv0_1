# Tasks

Each task is a directory containing:
- `task.yaml` — full schema (see `tasks/_template/task.yaml`)
- `verifier.py` — exports `verify(worktree, trace) -> VerifierResult`
- `fixture/` (optional) — local fixture data not shared via the
  central `fixtures/` pool
- `README.md` (optional) — task-specific notes for reviewers

## Adding a new task

```bash
cp -r tasks/_template tasks/tNN_category/tNN_short_name/
$EDITOR tasks/tNN_category/tNN_short_name/task.yaml
# ... author verifier.py and any local fixture ...
python -m hermesbench validate tasks/tNN_category/tNN_short_name/
```

The `validate` subcommand checks: schema parse, fixture resolution,
verifier import, fixture-size lint, injection-pattern lint.

## Categories

| ID | Tool | Tasks | Status |
|---|---|---:|---|
| t01_terminal_smoke | terminal | 5 | shipped |
| t02_file_read | read_file | 6 | shipped |
| t03_patch_edit | patch | 5 | shipped |
| t04_search_grep | search_files | 5 | shipped |
| t05_write_new | write_file | 5 | shipped |
| t06_process_mgmt | process | 5 | shipped |
| t07_todo_plan | todo | 3 | shipped |
| t08_execute_code | execute_code | 5 | shipped |
| t09_web_lookup | web_search/extract (mocked) | 3 | shipped |
| t10_memory_facts | memory | 3 | shipped |
| t11_error_recovery | recovery rate | 3 | shipped |

**Total: 48 tasks across 11 categories.** See `project.md` §4
for the full taxonomy.
