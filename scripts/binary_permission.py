"""The one record that lets binary analysis (REA, Ghidra, IDA, decompilers) run
in this project. Written only after the user answered the /rea question.

  python scripts/binary_permission.py grant --program "<name or exe>" --basis "<own code | written permission | open source>" --who "<who said so>"
  python scripts/binary_permission.py refuse --program "<name or exe>"
  python scripts/binary_permission.py status

The Bash guard hook (scripts/hooks/guard_bash.py) blocks every binary tool
unless this file says allowed = true. The record also goes into docs/decisions.md.
"""
import argparse
import json
import os
import sys
from datetime import datetime

PATH = os.path.join("state", "binary-permission.json")
BASES = ("own code", "written permission", "open source")


def load():
    try:
        with open(PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def save(record):
    os.makedirs("state", exist_ok=True)
    with open(PATH, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2)
    os.makedirs("docs", exist_ok=True)
    with open(os.path.join("docs", "decisions.md"), "a", encoding="utf-8") as fh:
        if record["allowed"]:
            fh.write(f"\n- {record['when']}: binary analysis ALLOWED for {record['program']}: {record['basis']} (stated by {record['who']}). "
                     f"Findings go to docs/raw/binary/; no decompiled code is copied into app/.\n")
        else:
            fh.write(f"\n- {record['when']}: binary analysis REFUSED for {record['program']}: no ownership or permission. The kit stays outside-only.\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("grant")
    g.add_argument("--program", required=True)
    g.add_argument("--basis", required=True, choices=BASES)
    g.add_argument("--who", required=True)
    r = sub.add_parser("refuse")
    r.add_argument("--program", required=True)
    sub.add_parser("status")
    a = ap.parse_args()
    if a.cmd == "status":
        p = load()
        if not p:
            print("Binary analysis: not decided yet (run /rea).")
        elif p.get("allowed"):
            print(f"Binary analysis: ALLOWED for {p['program']} ({p['basis']}, stated by {p['who']} on {p['when']}).")
        else:
            print(f"Binary analysis: REFUSED for {p['program']} on {p['when']}. The kit stays outside-only.")
        return 0
    when = datetime.now().strftime("%Y-%m-%d %H:%M")
    if a.cmd == "grant":
        save({"allowed": True, "program": a.program, "basis": a.basis, "who": a.who, "when": when})
        print(f"Recorded: binary analysis allowed for {a.program} ({a.basis}).")
    else:
        save({"allowed": False, "program": a.program, "when": when})
        print(f"Recorded: binary analysis refused for {a.program}. REA stays blocked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
