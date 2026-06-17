# Changelog

## v0.2.0 (2026-06-17)

### Added
- Real hermes-agent integration (`--real-agent` flag on `run`)
- Auto-installer (`install.sh`) with cross-platform dependency detection
- Config file system (`hermesbench.yaml`) — set model/endpoint once
- `serve` command — launch vLLM with correct benchmark flags
- `render` command — convert .cast to .gif or .mp4
- `export-sft` command — traces to SFT JSONL with loss masks
- `compare` command — side-by-side model comparison
- `record` command — 5-pane hyperframes video with live GPU telemetry
- `post-process` command — trim, thumbnail, highlight extraction
- `score --by-category` — per-category pass rate breakdown
- `score --html` — standalone dark-themed HTML report
- `run --results-dir` — custom output directory
- `run --n-runs` — run each task N times for variance
- `run --resume` — resume from crashed run (skip completed tasks)
- Live metrics panel with GPU power/temp/util sparklines + J/token
- Full test suite for config, SFT export, and scoring

### Fixed
- Replaced hardcoded `fake_hermes.py` with real agent option
- `score` now aggregates across multiple run directories
- `stats` command fully implemented (was stub)
- All CLI commands documented in README now exist

### Backward Compatible
- Fake agent mode remains the default (`--real-agent` is opt-in)
- Existing tests pass without modification
- `run` command signature backward compatible (new args have defaults)
