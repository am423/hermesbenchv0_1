"""A broken Python file that the model must fix."""
from __future__ import annotations


def divide(a: float, b: float) -> float:
    # Bug: no zero-division check
    return a / b
