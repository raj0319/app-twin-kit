"""Replay explicit allowlisted UIA actions against one pinned source process."""

from pathlib import Path
from tempfile import gettempdir
from time import sleep

from .desktop import (
    KEYS,
    SECRET,
    capture_window,
    control_for,
    dialog_for,
    dialog_text,
    identity,
    invoke_async,
    menu_item,
    read_control,
    send_keys_scoped,
    settle,
    tree,
    utc,
    wait_closed,
    window_for,
)
from .run_state import atomic_json, audit, exclusive

READ_ONLY = {"observe", "read", "screenshot", "ocr_read"}
MUTATING = {"click", "fill", "select", "focus", "menu", "dialog_click", "keys", "ocr_click"}
CAPTURING = {"screenshot", "ocr_read", "ocr_click"}


def allow_key(step):
    """The allowlist key of a step. menu: "File>Save"; dialog_click: "Confirm save|Yes";
    keys: "<automation_id or window>:<keys>"; ocr_click: "<automation_id>:<label>"; others: the
    automation ID."""
    action = step["action"]
    if action == "menu":
        return ">".join(step.get("path") or [])
    if action == "dialog_click":
        return f"{step.get('dialog', '')}|{step.get('button', '')}"
    if action == "keys":
        return f"{step.get('automation_id') or 'window'}:{step.get('value', '')}"
    if action == "ocr_click":
        return f"{step.get('automation_id', '')}:{step.get('label', '')}"
    return step.get("automation_id")


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
        key = allow_key(step)
        if action in {"menu", "dialog_click"} and (not key or SECRET.search(key)):
            raise ValueError("invalid or sensitive menu path or dialog button")
        if action == "keys" and not KEYS.fullmatch(str(step.get("value", ""))):
            raise ValueError("keys must use the safe subset (no Alt)")
        if action in {"ocr_click", "ocr_read"}:
            label = step.get("label", "")
            if not target or (
                action == "ocr_click" and (not label or len(label) > 40 or SECRET.search(label))
            ):
                raise ValueError("OCR steps need an automation_id and, for a click, a short label")
            if not 0.5 <= float(step.get("min_confidence", 0.8)) <= 1:
                raise ValueError("min_confidence must be between 0.5 and 1")
        if action in MUTATING:
            if not (allow_mutation and sandbox_confirmed and key and (action, key) in allowed_targets):
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
    if any(step["action"] in {"ocr_read", "ocr_click"} for step in plan) and not (
        sandbox_confirmed and out_path
    ):
        raise PermissionError("OCR captures need a disposable source and an evidence directory")
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
        event = {
            "id": identity(index, action, selector, allow_key(step)),
            "at": utc(),
            "step": index,
            "action": action,
            "automation_id": selector,
        }
        if action in {"menu", "dialog_click"}:
            event["target"] = allow_key(step)
        if action in MUTATING and action != "dialog_click" and not settle(2.0):
            event["unsettled_before"] = True  # an earlier blocked click is still running
        if out_path:
            audit(journal, "started", event)
        if action == "menu":
            item = menu_item(window, step["path"])
            if not item.is_enabled():
                raise PermissionError("disabled source menu item")
            event["invoke"] = invoke_async(item)
            target = window
        elif action == "dialog_click":
            dialog = dialog_for(window, step["dialog"])
            event["dialog_text"] = dialog_text(dialog)
            buttons = [
                b
                for b in dialog.descendants(control_type="Button")
                if b.element_info.name.replace("&", "") == step["button"]
            ]
            if len(buttons) != 1:
                raise RuntimeError(
                    f"expected one {step['button']!r} button in the dialog, found {len(buttons)}"
                )
            event["invoke"] = invoke_async(buttons[0])
            # The click that opened the dialog only returns once its handler has finished.
            event["settled"] = wait_closed(dialog) and settle()
            target = window
        elif action == "keys":
            target = control_for(window, selector) if selector else window
            send_keys_scoped(target if selector else None, window, step["value"])
        elif action in {"ocr_click", "ocr_read"}:
            from .ocr import click_label, read_text

            target = control_for(window, selector)
            image = out_path.with_name(f"{out_path.stem}-ocr-{index:03}.png")
            if action == "ocr_read":
                event["ocr"] = read_text(window, target, image)
                event["value"] = event["ocr"]["text"]
            else:
                event["ocr"] = click_label(
                    window, target, step["label"], image, float(step.get("min_confidence", 0.8))
                )
        else:
            target = control_for(window, selector)
        if action in {"click", "fill", "select", "focus"}:
            if not target.is_enabled() or SECRET.search(target.element_info.name or ""):
                raise PermissionError("disabled or sensitive source control")
            if action == "click":
                event["invoke"] = invoke_async(target)
            elif action == "fill":
                target.iface_value.SetValue(step["value"])
            elif action == "select":
                target.select(step["value"])
            elif action == "focus":
                target.set_focus()
        if action in MUTATING:
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
