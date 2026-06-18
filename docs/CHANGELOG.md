# Changelog

All notable changes to HermesBench are documented here.

## [0.3.0] — 2026-06-18

### Changed

- **`hermesbench run` defaults to the real Hermes engine** (`run_real.py` / `run_agent.py`); use `--engine legacy` for the original tmux + statsd runner.
- **HyperFrames reporting** via `hermesbench report` (REPORT.md, event timeline, optional `--render-video`).
- **51 tasks** in the suite (48 core categories plus 3 `t12_real_world` integration tasks).

### Added

- `scripts/bootstrap.sh` clone-and-run venv setup; `install.sh` delegates Python bootstrap to it.
- `hermesbench doctor --install`, `hermesbench setup`, and expanded preflight for real runs.
- Documentation: `AGENTS.md`, `docs/GETTING_STARTED.md`, `docs/PROVIDERS.md`.

### Deprecated

- `hermesbench run-real` — alias for `hermesbench run` (real engine).

[0.3.0]: https://github.com/am423/hermes-bench-tool-call/compare/v0.2.0...v0.3.0

## [0.3.1] — 2026-06-18

### Added

- **Resume for real engine** — `--resume <run_id>` or `--run-id … --resume-skipped` skips tasks with PASS/FAIL in `results/<run_id>/summary.json` and merges new rows.
- `docs/RUN_LAYOUT.md` — artifact paths and resume semantics (real vs legacy).
- `presets/README.md` and `presets/weak_categories_grok.json` — weak-category rerun examples.
- Unit tests for resume skip logic (`tests/test_run_real_resume.py`).

### Changed

- `AGENTS.md` — canonical repo, 51 tasks, `--engine`, score paths, resume section.