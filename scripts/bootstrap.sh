#!/usr/bin/env bash
# Clone-and-run bootstrap for hermesbench (creates .venv, editable install).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required (3.11+)" >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -U pip
.venv/bin/pip install -e .

echo ""
echo "Bootstrap complete."
echo "  source .venv/bin/activate"
echo "  hermesbench doctor --install"
echo "  hermesbench setup --hermes --check-only"
echo ""
.venv/bin/python -m hermesbench doctor --install || true