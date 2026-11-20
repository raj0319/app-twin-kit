"""Bounded, read-only UI Automation capture."""

import platform

from .desktop import redact, tree, window_for
from .run_state import atomic_json


def explore(title, output, *, pid=None, max_controls=500, max_depth=8):
    if platform.system() != "Windows":
        raise RuntimeError("Windows UI Automation exploration requires a Windows desktop")
    if not 1 <= max_controls <= 5000 or not 1 <= max_depth <= 20:
        raise ValueError("invalid exploration limits")
    snapshot = tree(window_for(title, pid), limit=max_controls, depth_limit=max_depth)
    snapshot.update(title=redact(title), status="read_only_observation")
    atomic_json(output, snapshot)
    return snapshot
