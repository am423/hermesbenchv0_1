#!/usr/bin/env python3
"""Shim — use: hermesbench run-real or python -m hermesbench.run_real"""
from hermesbench.run_real import main

if __name__ == "__main__":
    raise SystemExit(main())