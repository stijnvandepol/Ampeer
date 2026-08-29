"""Ampeer simulation core.

This package must remain free of Django imports and of I/O. External data
enters through the protocols in ``ampeer_sim.providers``.
"""

from __future__ import annotations

ENGINE_VERSION = "0.4.0"

__all__ = ["ENGINE_VERSION"]
