"""Propose conservative action pairs from a versioned inventory and observed UIA IDs."""

import re
from pathlib import Path

from .run_state import atomic_json
from .uas import UniversalAppSpec


def build_pair(spec, workflow, steps, observations, *, approved_fixture=False):
    controls = {control.automation_id: control for screen in spec.screens for control in screen.controls}
    targets = {step["automation_id"] for step in steps} | observations.keys()
    missing = targets - controls.keys()
    if missing or any(not re.fullmatch(r"[a-z][a-z0-9_]*", target) for target in targets):
        raise ValueError(f"no deterministic selector for targets: {sorted(missing or targets)}")
    browser = [
        {
            "action": step["action"],
            "selector": "#" + step["automation_id"],
            **({"value": step["value"]} if "value" in step else {}),
            **({"wait_for": "#status"} if step.get("wait_for_status") else {}),
        }
        for step in steps
        if step["action"] in {"click", "select", "fill"}
    ]
    return {
        "id": workflow.id,
        "windows": steps,
        "browser": {"path": "/", "steps": browser},
        "observations": {
            key: {"windows_automation_id": key, "browser_selector": "#" + key, "normalize": kind}
            for key, kind in observations.items()
        },
        "status": "user_approved_not_behavior_verified" if approved_fixture else "proposed_unverified",
        "evidence_ids": sorted({ref for control in targets for ref in controls[control].evidence_ids}),
    }


def propose_pairs(spec_file, output_file):
    spec = UniversalAppSpec.load(spec_file)
    proposals = []
    gaps = []
    for item in spec.workflows:
        try:
            steps = [step for step in item.steps if step.get("action") != "observe"]
            observations = {
                step["automation_id"]: step.get("normalize", "text")
                for step in item.steps
                if step.get("action") == "observe"
            }
            if not steps or not observations:
                raise ValueError("both an action sequence and observation are required")
            proposals.append(build_pair(spec, item, steps, observations))
        except (ValueError, KeyError) as exc:
            gaps.append({"id": item.id, "reason": str(exc)})
    atomic_json(output_file, proposals)
    return {"proposals": len(proposals), "file": str(Path(output_file)), "gaps": gaps}
