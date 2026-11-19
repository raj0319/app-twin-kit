"""Print a one-screen status of the App Twin project. Read only."""
import glob
import json
import os
import re
import sys


def count(pattern):
    # *.live.md and *.watcher.md are side copies of a screen (App Watcher vs live app), not extra screens
    return len([f for f in glob.glob(pattern) if not f.lower().endswith((".live.md", ".watcher.md"))])


def main():
    mode = "not started"
    if os.path.exists("state/mode.json"):
        try:
            with open("state/mode.json", encoding="utf-8") as fh:
                mode = json.load(fh).get("mode", mode)
        except Exception:
            pass
    app = "not set"
    if os.path.exists("state/project.json"):
        try:
            with open("state/project.json", encoding="utf-8") as fh:
                app = json.load(fh).get("app_name", app)
        except Exception:
            pass

    screens = count("docs/raw/screens/*.md")
    tasks = count("docs/raw/tasks/*.md")
    spec = count("docs/spec/*.md")
    gaps = {"blocks work": 0, "wrong result": 0, "cosmetic": 0}
    if os.path.exists("docs/verify/gaps.md"):
        with open("docs/verify/gaps.md", encoding="utf-8") as fh:
            text = fh.read()
        for block in re.split(r"\n(?=### Gap:)", text):
            if "**Status:** open" not in block:
                continue
            for sev in gaps:
                if re.search(rf"\*\*Severity:\*\*\s*{sev}", block):
                    gaps[sev] += 1
    passed = failed = 0
    if os.path.exists("docs/verify/report.md"):
        with open("docs/verify/report.md", encoding="utf-8") as fh:
            for line in fh:
                if "| PASS |" in line:
                    passed += 1
                elif "| FAIL |" in line:
                    failed += 1

    print(f"App:        {app}")
    print(f"Mode:       {mode}")
    print(f"Screens:    {screens} recorded")
    print(f"Tasks:      {tasks} recorded, {spec} in spec")
    print(f"Verify:     {passed} pass, {failed} fail")
    print(
        f"Open gaps:  {gaps['blocks work']} blocks work, "
        f"{gaps['wrong result']} wrong result, {gaps['cosmetic']} cosmetic"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
