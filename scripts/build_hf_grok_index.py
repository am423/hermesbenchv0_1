#!/usr/bin/env python3
"""CLI shim — logic in hermesbench.hf_video."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hermesbench.hf_video import DEFAULT_OUT_DIR, DEFAULT_TEMPLATE, generate_hf_index

REPO = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeline", type=Path, required=True)
    ap.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = ap.parse_args()
    tl = json.loads(args.timeline.read_text(encoding="utf-8"))
    path = generate_hf_index(tl, template_path=args.template, out_dir=args.out_dir)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())