"""Live check of menu, native dialog and scoped keyboard actions on the self-authored WinForms fixture.

python -m fixtures.windows.menus_demo state/menus-run --repeat 3
Every run uses a new disposable fixture folder and a new evidence folder.
"""

import argparse
import json
import tempfile
from pathlib import Path

from engine.desktop import window_for
from engine.run_state import atomic_json
from engine.windows_actions import execute_plan, validate_plan

from .demo import LOCAL, fixture, wait_until

TITLE = "ZZTEST App Twin Menus"
PLAN = [
    {"action": "fill", "automation_id": "note", "value": "ZZTEST note"},
    {"action": "menu", "path": ["File", "Save"]},
    {"action": "dialog_click", "dialog": "Confirm save", "button": "Yes"},
    {"action": "observe", "automation_id": "status"},
    {"action": "keys", "automation_id": "note", "value": "^k"},
    {"action": "observe", "automation_id": "status"},
    {"action": "menu", "path": ["File", "New"]},
    {"action": "observe", "automation_id": "status"},
    {"action": "menu", "path": ["File", "Save"]},
    {"action": "dialog_click", "dialog": "Confirm save", "button": "No"},
    {"action": "observe", "automation_id": "status"},
]
ALLOWED = {
    ("fill", "note"),
    ("menu", "File>Save"),
    ("menu", "File>New"),
    ("dialog_click", "Confirm save|Yes"),
    ("dialog_click", "Confirm save|No"),
    ("keys", "note:^k"),
}
EXPECTED = ["Saved", "Shortcut Ctrl+K", "New note", "Save cancelled"]


def refusals():
    """Plans that must be refused before anything is sent to the source."""
    cases = {
        "unlisted dialog button": [{"action": "dialog_click", "dialog": "Confirm save", "button": "Cancel"}],
        "Alt+F4 keys": [{"action": "keys", "value": "%{F4}"}],
        "unlisted menu": [{"action": "menu", "path": ["File", "Exit"]}],
    }
    result = {}
    for name, plan in cases.items():
        try:
            validate_plan(plan, allow_mutation=True, sandbox_confirmed=True, allowed_targets=ALLOWED)
            result[name] = "ACCEPTED"
        except (PermissionError, ValueError) as exc:
            result[name] = f"refused: {type(exc).__name__}"
    return result


def run_once(output):
    work = Path(tempfile.mkdtemp(prefix="source-", dir=output))
    with fixture(
        [str(LOCAL / "menus-dialogs.ps1"), "-FixtureDirectory", str(work)], TITLE, work / "app.log"
    ) as app:
        wait_until(lambda: window_for(TITLE, app.pid), app)
        trace = execute_plan(
            TITLE,
            PLAN,
            pid=app.pid,
            allow_mutation=True,
            sandbox_confirmed=True,
            allowed_targets=ALLOWED,
            out_path=work / "trace.json",
        )
    seen = [event["value"] for event in trace["observations"] if event["action"] == "observe"]
    saved = (
        (work / "notes.txt").read_text(encoding="utf-8-sig").strip()
        if (work / "notes.txt").exists()
        else None
    )
    return {
        "evidence": str(work),
        "status_sequence": seen,
        "dialogs": [e.get("dialog_text") for e in trace["observations"] if e["action"] == "dialog_click"],
        "invoke": [e.get("invoke") for e in trace["observations"] if "invoke" in e],
        "saved_file": saved,
        "passed": seen == EXPECTED and saved == "ZZTEST note",
    }


OCR_PLAN = [
    {"action": "ocr_read", "automation_id": "pad"},
    {"action": "ocr_click", "automation_id": "pad", "label": "HIGH"},
    {"action": "observe", "automation_id": "status"},
    {"action": "ocr_click", "automation_id": "pad", "label": "MEDIUM"},
    {"action": "observe", "automation_id": "status"},
]
OCR_ALLOWED = {("ocr_click", "pad:HIGH"), ("ocr_click", "pad:MEDIUM"), ("ocr_click", "pad:URGENT")}


def run_ocr(output):
    """Owner-drawn pad: no UIA children, so labels are found by Windows OCR and clicked by position."""
    work = Path(tempfile.mkdtemp(prefix="ocr-", dir=output))
    with fixture(
        [str(LOCAL / "menus-dialogs.ps1"), "-FixtureDirectory", str(work)], TITLE, work / "app.log"
    ) as app:
        wait_until(lambda: window_for(TITLE, app.pid), app)
        trace = execute_plan(
            TITLE,
            OCR_PLAN,
            pid=app.pid,
            allow_mutation=True,
            sandbox_confirmed=True,
            allowed_targets=OCR_ALLOWED,
            out_path=work / "trace.json",
        )
        try:
            execute_plan(
                TITLE,
                [{"action": "ocr_click", "automation_id": "pad", "label": "URGENT"}],
                pid=app.pid,
                allow_mutation=True,
                sandbox_confirmed=True,
                allowed_targets=OCR_ALLOWED,
                out_path=work / "missing-label.json",
            )
            missing = "CLICKED"
        except LookupError as exc:
            missing = json.loads(str(exc))
    events = trace["observations"]
    seen = [e["value"] for e in events if e["action"] == "observe"]
    clicks = [e["ocr"] for e in events if e["action"] == "ocr_click"]
    read = next(e["ocr"] for e in events if e["action"] == "ocr_read")
    return {
        "evidence": str(work),
        "ocr_text": read["text"],
        "scale": read["scale"],
        "clicks": [{k: c[k] for k in ("label", "confidence", "matches", "center")} for c in clicks],
        "status_sequence": seen,
        "missing_label": missing,
        "passed": seen == ["Priority HIGH", "Priority MEDIUM"]
        and all(c["confidence"] >= 0.8 for c in clicks)
        and isinstance(missing, dict)
        and missing.get("needs_review") is True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()
    output = args.directory.resolve()
    output.mkdir(parents=True, exist_ok=False)
    repeat = max(1, min(args.repeat, 10))
    runs = [run_once(output) for _ in range(repeat)]
    ocr = [run_ocr(output) for _ in range(repeat)]
    report = {
        "refusals": refusals(),
        "runs": runs,
        "ocr_runs": ocr,
        "passed": sum(r["passed"] for r in runs + ocr),
        "total": len(runs) + len(ocr),
    }
    atomic_json(output / "report.json", report)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] == report["total"] and "ACCEPTED" not in report["refusals"].values() else 1


if __name__ == "__main__":
    raise SystemExit(main())
