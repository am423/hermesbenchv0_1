# Adding a new environment backend

hermesbench supports pluggable execution environments. v0.1 ships
`tmux_isolated`; you can add a new one in three steps.

## 1. Subclass `BaseHermesBenchEnvironment`

`hermesbench/backend/base.py` defines the ABC:

```python
from hermesbench.backend.base import (
    BaseHermesBenchEnvironment,
    CommandResult,
)
from hermesbench.backend.registry import register_backend


@register_backend("my_backend")
class MyBackend(BaseHermesBenchEnvironment):
    def init_session(self) -> None:
        # Bring up the environment (start a container, VM, ssh session, etc.)
        # Apply any per-task setup (ulimit, plugin allowlist, latency).
        ...

    def run(self, cmd: str, *, timeout: int = 120) -> CommandResult:
        # Run a single command. Must respect CWD = self.worktree.
        # Return a CommandResult with exit_code, stdout, stderr, etc.
        ...

    def cleanup(self) -> None:
        # Tear down. Idempotent and signal-safe.
        ...
```

`init_session()` is called once before any `run()` call. `cleanup()`
runs in a `finally:` block in the runner — make sure it doesn't raise
if called twice.

## 2. Register the backend

The `@register_backend("my_backend")` decorator adds the class to the
global registry. Import the module somewhere in
`hermesbench/backend/__init__.py` so the registry is populated on
package import:

```python
# hermesbench/backend/__init__.py
from hermesbench.backend import tmux_isolated  # noqa: F401
from hermesbench.backend import my_backend    # noqa: F401  <-- add this
```

## 3. Use it from the CLI

```bash
python -m hermesbench run --task ... --backend my_backend
```

The runner selects the backend via `--backend` (default: `tmux_isolated`).

## Design checklist

- [ ] `init_session` is idempotent (safe to call twice)
- [ ] `cleanup` is idempotent and signal-safe
- [ ] `run` returns within `timeout` even if the command hangs
- [ ] `run` correctly populates `CommandResult.exit_code`
- [ ] CWD = `self.worktree` for every command
- [ ] Per-task `ulimit` enforced if you spawn a shell (Q48)
- [ ] `DISABLED_TOOLSETS` from `self.plugin_allowlist` injected (Q54)
- [ ] Latency injection supported via `self.latency_injection_ms` (Q59)

## Reference: TmuxIsolatedEnvironment

`hermesbench/backend/tmux_isolated.py` is the canonical reference
implementation — ~310 LOC. Read it first to see the full lifecycle
(worktree creation → tmux session → ulimit → plugin allowlist →
recorder pipe-pane → run() with sentinel-based output capture →
cleanup).
