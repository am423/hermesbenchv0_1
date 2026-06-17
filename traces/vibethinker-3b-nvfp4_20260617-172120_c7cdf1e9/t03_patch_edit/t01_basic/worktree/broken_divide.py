"""A broken Python file that the model must fix."""
from __future__ import annotations


def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError('division by zero')
    return a / b
