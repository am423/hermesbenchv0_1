#!/usr/bin/env python3
"""CLI shim — logic in hermesbench.event_timeline."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hermesbench.event_timeline import write_event_timeline


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--video-duration", type=float, default=105.0)
    args = ap.parse_args()
    out = write_event_timeline(args.summary, args.out, video_duration=args.video_duration)
    print(f"wrote {args.out} ({len(out['events'])} events, pass_rate={out['pass_rate']:.1%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())