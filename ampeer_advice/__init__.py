"""Ampeer advice layer.

Turns a simulation result into an explainable recommendation. Like
``ampeer_sim`` this package imports no Django and performs no I/O, for the same
reason: a wrong advice produces no error message, only a confident sentence.
"""

from __future__ import annotations

ADVICE_VERSION = "0.1.0"

__all__ = ["ADVICE_VERSION"]
