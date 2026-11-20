"""Turn repeated read-only Windows UIA snapshots into evidence-backed transitions.

No clicks or mutations are performed. A transition is an observed difference,
not proof of a business rule or a validated workflow.
"""

import hashlib
import json
from pathlib import Path


def _index(snapshot):
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("controls"), list):
        raise ValueError("invalid Windows snapshot")
    result = {}
    for c in snapshot["controls"]:
        if not isinstance(c, dict):
            continue
        key = (str(c.get("automation_id", "")), str(c.get("control_type", "")), str(c.get("name", "")))
        if not key[0] and not key[2]:
            continue
        result[key] = {"enabled": bool(c.get("enabled")), "visible": bool(c.get("visible"))}
    return result


def transitions(snapshots):
    if not 2 <= len(snapshots) <= 100:
        raise ValueError("provide 2 to 100 snapshots")
    rows = []
    for i in range(1, len(snapshots)):
        before, after = _index(snapshots[i - 1]), _index(snapshots[i])
        changes = []
        for key in sorted(before.keys() | after.keys()):
            a, b = before.get(key), after.get(key)
            if a == b:
                continue
            changes.append(
                {
                    "automation_id": key[0],
                    "control_type": key[1],
                    "name": key[2],
                    "change": "appeared" if a is None else "disappeared" if b is None else "state_changed",
                    "before": a,
                    "after": b,
                }
            )
        digest = hashlib.sha256(json.dumps(changes, sort_keys=True).encode()).hexdigest()[:16]
        rows.append(
            {
                "from_snapshot": i - 1,
                "to_snapshot": i,
                "id": f"transition-{digest}",
                "changes": changes,
                "status": "observed_unattributed",
            }
        )
    return rows


def analyze_files(paths, output):
    snapshots = [json.loads(Path(p).read_text(encoding="utf-8")) for p in paths]
    result = {
        "transitions": transitions(snapshots),
        "verified_workflows": 0,
        "warning": "Changes alone cannot identify the action that caused them",
    }
    p = Path(output)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result
