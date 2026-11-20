"""Propose conservative action pairs from a versioned inventory and observed UIA IDs.

Source controls are resolved to the generated browser IDs automatically only when the match is
predictable: the same ID, the same ID once naming style and common Windows prefixes are removed, or a
unique visible-label match. Every resolution records its method. Anything ambiguous or unmatched is
reported for review with its candidates instead of being guessed.
"""

import re
from pathlib import Path

from .run_state import atomic_json
from .uas import UniversalAppSpec

SAFE_ID = re.compile(r"[a-z][a-z0-9_]*")
ACTIONS = ("entry", "records", "calculate", "save", "confirm_save")
# Hungarian-style prefixes common in WinForms, VB6, Delphi and WPF code-behind names.
PREFIXES = (
    "txt",
    "tb",
    "edt",
    "btn",
    "cmd",
    "cmb",
    "cbo",
    "cb",
    "chk",
    "lbl",
    "num",
    "nud",
    "dtp",
    "lst",
    "grd",
)
BUTTON_ROLES = {"button", "splitbutton", "hyperlink", "menuitem", "link"}


def snake(value):
    value = re.sub(r"[&:*]", "", value or "").strip()
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", value)
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def unprefixed(value):
    """txtUnitPrice, txt_unit_price -> unit_price; an all-lowercase txtunitprice is left alone."""
    parts = snake(value).split("_")
    return "_".join(parts[1:] if len(parts) > 1 and parts[0] in PREFIXES else parts)


def browser_targets(spec):
    """Every element ID the generator emits, with the kind of control it is."""
    targets = {name: "action" for name in ACTIONS}
    targets["status"] = "output"
    for entity in spec.entities:
        for field in entity.fields:
            targets.setdefault(field, "input")
            targets.setdefault("latest_" + field, "output")
    return targets


def _fits(role, kind):
    role = (role or "").lower()
    if kind == "action":
        return role in BUTTON_ROLES or not role
    if kind == "input":
        return role not in BUTTON_ROLES
    return True


def resolve(control, targets, observed=False):
    """Map one source control to a browser ID. Returns (browser_id, method) or raises ValueError with the
    candidates a reviewer should choose from."""
    automation_id = control.automation_id or ""
    usable = {
        key: kind
        for key, kind in targets.items()
        if observed or (kind != "output" and _fits(control.role, kind))
    }
    for method, key in (
        ("exact_id", automation_id),
        ("normalized_id", snake(automation_id)),
        ("unprefixed_id", unprefixed(automation_id)),
    ):
        if key and key in usable:
            return key, method
    label = snake(control.name)
    if label and label in usable:
        return label, "unique_label"
    tokens = set(unprefixed(automation_id).split("_")) | set(label.split("_"))
    tokens.discard("")
    candidates = sorted(key for key in usable if tokens & set(key.split("_")))
    reason = "ambiguous" if len(candidates) > 1 else "no predictable match"
    if len(candidates) == 1:
        reason = "single partial match needs review"
    raise ValueError(
        f"{reason} for source control {automation_id or control.name!r}; candidates: {candidates or 'none'}"
    )


def build_pair(spec, workflow, steps, observations, *, approved_fixture=False):
    controls = {control.automation_id: control for screen in spec.screens for control in screen.controls}
    targets = {step["automation_id"] for step in steps} | observations.keys()
    missing = targets - controls.keys()
    if missing:
        raise ValueError(f"no captured source control for targets: {sorted(missing)}")
    available = browser_targets(spec)
    resolution = {}
    review = []
    for target in sorted(targets):
        try:
            browser_id, method = resolve(controls[target], available, observed=target in observations)
        except ValueError as exc:
            review.append(str(exc))
            continue
        if not SAFE_ID.fullmatch(browser_id):
            review.append(f"browser ID {browser_id!r} for {target!r} is not a safe selector")
            continue
        resolution[target] = {"browser_id": browser_id, "method": method}
    if review:
        raise ValueError("; ".join(review))
    browser = [
        {
            "action": step["action"],
            "selector": "#" + resolution[step["automation_id"]]["browser_id"],
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
            key: {
                "windows_automation_id": key,
                "browser_selector": "#" + resolution[key]["browser_id"],
                "normalize": kind,
            }
            for key, kind in observations.items()
        },
        "resolution": resolution,
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
    automatic = sum(
        1 for pair in proposals for row in pair["resolution"].values() if row["method"] != "exact_id"
    )
    return {
        "proposals": len(proposals),
        "file": str(Path(output_file)),
        "gaps": gaps,
        "resolved_automatically": automatic,
        "needs_review": len(gaps),
    }
