"""Read-only Windows application accessibility capability inventory."""

import platform
from pathlib import Path

from .run_state import atomic_json


def inspect(title, output):
    if platform.system() != "Windows":
        raise RuntimeError("Windows desktop required for live compatibility inventory")
    from .windows_explorer import explore

    snapshot = explore(title, output)
    controls = snapshot["controls"]
    named = sum(bool(c.get("name")) for c in controls)
    ids = sum(bool(c.get("automation_id")) for c in controls)
    types = {}
    for control in controls:
        kind = control.get("control_type", "unknown")
        types[kind] = types.get(kind, 0) + 1
    result = {
        "title": title,
        "controls": len(controls),
        "named_controls": named,
        "identified_controls": ids,
        "control_types": types,
        "truncated": snapshot["truncated"],
        "warning": "Custom-drawn, inaccessible and virtualized controls may require manual adapters",
    }
    atomic_json(Path(output).with_name("compatibility-report.json"), result)
    return result
