"""Replay explicit allowlisted UIA actions against one pinned source process."""

from pathlib import Path
from tempfile import gettempdir
from time import sleep

from .desktop import SECRET, capture_window, control_for, identity, read_control, tree, utc, window_for
from .run_state import atomic_json, audit, exclusive

READ_ONLY = {"observe", "read", "screenshot"}
MUTATING = {"click", "fill", "select", "focus"}


def validate_plan(plan, *, allow_mutation=False, sandbox_confirmed=False, allowed_targets=()):
    if not isinstance(plan, list) or not 1 <= len(plan) <= 100:
        raise ValueError("plan must contain 1 to 100 steps")
    for step in plan:
        if not isinstance(step, dict) or step.get("action") not in READ_ONLY | MUTATING:
            raise ValueError("unsupported Windows action")
        action = step["action"]
        target = step.get("automation_id")
        if target is not None and (not isinstance(target, str) or SECRET.search(target)):
            raise ValueError("invalid or sensitive Windows target")
        if action in MUTATING:
            if not (allow_mutation and sandbox_confirmed and target and (action, target) in allowed_targets):
                raise PermissionError(
                    "fixture consent and an exact allowlisted action/control pair are required"
                )
        if action == "fill" and (not isinstance(step.get("value"), str) or len(step["value"]) > 200):
            raise ValueError("fill requires bounded string input")
    return True


def execute_plan(
    title,
    plan,
    *,
    pid=None,
    allow_mutation=False,
    sandbox_confirmed=False,
    allowed_targets=(),
    out_path=None,
    screenshots=False,
    observations=None,
):
    with exclusive(Path(gettempdir()) / "app-twin-kit" / "desktop.lock"):
        return _execute(
            title,
            plan,
            pid,
            allow_mutation,
            sandbox_confirmed,
            allowed_targets,
            out_path,
            screenshots,
            observations,
        )


def _execute(
    title, plan, pid, allow_mutation, sandbox_confirmed, allowed_targets, out_path, screenshots, observations
):
    validate_plan(
        plan,
        allow_mutation=allow_mutation,
        sandbox_confirmed=sandbox_confirmed,
        allowed_targets=allowed_targets,
    )
    if any(step["action"] in MUTATING for step in plan) and (pid is None or out_path is None):
        raise PermissionError("fixture actions require explicit PID and a write-ahead journal")
    if screenshots and not (sandbox_confirmed and out_path):
        raise PermissionError("screenshot capture requires a disposable source and evidence directory")
    if any(step["action"] == "screenshot" for step in plan) and not screenshots:
        raise PermissionError("screenshot capture is disabled")
    window = window_for(title, pid)
    entries = []
    initial = tree(window)
    previous_state = initial["state_id"]
    edges = []
    if out_path:
        out_path = Path(out_path)
        journal = out_path.with_suffix(".jsonl")
        if journal.exists():
            raise RuntimeError(
                "replay evidence already exists; reset the fixture and use a new evidence directory"
            )
    for index, step in enumerate(plan):
        action = step["action"]
        selector = step.get("automation_id")
        target = control_for(window, selector)
        event = {
            "id": identity(index, action, selector),
            "at": utc(),
            "step": index,
            "action": action,
            "automation_id": selector,
        }
        if out_path:
            audit(journal, "started", event)
        if action in MUTATING:
            if not target.is_enabled() or SECRET.search(target.element_info.name or ""):
                raise PermissionError("disabled or sensitive source control")
            if action == "click":
                target.invoke()
            elif action == "fill":
                target.iface_value.SetValue(step["value"])
            elif action == "select":
                target.select(step["value"])
            elif action == "focus":
                target.set_focus()
            sleep(0.12)  # UIA Invoke may schedule work on the target dispatcher.
        event["state"] = tree(window)
        next_state = event["state"]["state_id"]
        if next_state != previous_state:
            edges.append({"from": previous_state, "to": next_state, "event_id": event["id"]})
        previous_state = next_state
        if action in {"observe", "read"} and selector:
            event["value"] = read_control(target)
        if screenshots:
            image_path = out_path.with_name(f"{out_path.stem}-{index:03}.png")
            image_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                capture_window(window, image_path)
                event["screenshot"] = image_path.name
            except OSError as exc:
                event["screenshot_unavailable"] = str(exc)
        entries.append(event)
        if out_path:
            audit(journal, "finished", {"id": event["id"], "state": event["state"]["state_id"]})
    values = {
        name: read_control(control_for(window, selector)) for name, selector in (observations or {}).items()
    }
    result = {
        "pid": window.process_id(),
        "initial_state": initial,
        "transitions": edges,
        "observations": entries,
        "values": values,
    }
    if out_path:
        atomic_json(out_path, result)
    return result
