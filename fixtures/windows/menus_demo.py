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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args()
    output = args.directory.resolve()
    output.mkdir(parents=True, exist_ok=False)
    runs = [run_once(output) for _ in range(max(1, min(args.repeat, 10)))]
    report = {
        "refusals": refusals(),
        "runs": runs,
        "passed": sum(r["passed"] for r in runs),
        "total": len(runs),
    }
    atomic_json(output / "report.json", report)
    print(json.dumps(report, indent=2))
    return 0 if report["passed"] == report["total"] and "ACCEPTED" not in report["refusals"].values() else 1


if __name__ == "__main__":
    raise SystemExit(main())
