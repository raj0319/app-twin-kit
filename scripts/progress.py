"""One easy progress line with percent and approximate time left.

  python scripts/progress.py

Writes state/progress.json {"line", "percent", "eta_min"} for the status line mod
and prints the line. Estimates use the time since the mode started
(state/mode.json "since") and how many items are done so far.
"""
import glob
import json
import os
import re
import sys
from datetime import datetime


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def count(pattern):
    return len(glob.glob(pattern))


def discover():
    q = read_json("state/queue.json", [])
    total = len(q)
    done = sum(1 for e in q if e.get("status") == "done")
    durations = []
    for e in q:
        if e.get("started") and e.get("finished"):
            try:
                a = datetime.fromisoformat(e["started"])
                b = datetime.fromisoformat(e["finished"])
                durations.append((b - a).total_seconds())
            except Exception:
                pass
    avg = sum(durations) / len(durations) if durations else None
    return done, total, "screens", avg


def spec():
    total = count("docs/raw/screens/*.md") + count("docs/raw/tasks/*.md")
    done = count("docs/spec/*.md")
    return done, total, "spec files", None


def build():
    text = ""
    if os.path.exists("docs/build-plan.md"):
        with open("docs/build-plan.md", encoding="utf-8") as fh:
            text = fh.read()
    done = len(re.findall(r"^- \[x\]", text, re.M | re.I))
    total = done + len(re.findall(r"^- \[ \]", text, re.M))
    return done, total, "build items", None


def verify():
    total = count("docs/spec/task-*.md") or count("docs/spec/*.md")
    done = 0
    if os.path.exists("docs/verify/report.md"):
        with open("docs/verify/report.md", encoding="utf-8") as fh:
            done = sum(1 for l in fh if "| PASS |" in l or "| FAIL |" in l)
    return done, total, "tasks checked", None


def fix():
    text = ""
    if os.path.exists("docs/verify/gaps.md"):
        with open("docs/verify/gaps.md", encoding="utf-8") as fh:
            text = fh.read()
    total = text.count("### Gap:")
    open_ = text.count("**Status:** open")
    return total - open_, total, "gaps closed", None


def main():
    m = read_json("state/mode.json", {})
    mode = m.get("mode", "not started")
    since = m.get("since")
    fn = {"DISCOVER": discover, "SPEC": spec, "BUILD": build, "VERIFY": verify, "FIX": fix}.get(mode)
    if not fn:
        line = "Not started yet. Type /start."
        out = {"line": line, "percent": 0, "eta_min": None}
    else:
        done, total, unit, avg = fn()
        percent = int(done * 100 / total) if total else 0
        eta = None
        remaining = max(total - done, 0)
        if avg:
            eta = remaining * avg / 60
        elif since and done:
            try:
                elapsed = (datetime.now() - datetime.fromisoformat(since)).total_seconds()
                eta = remaining * (elapsed / done) / 60
            except Exception:
                eta = None
        if total == 0:
            eta_txt = "finding out how much there is"
        elif eta is None:
            eta_txt = "time estimate after the first few"
        elif eta < 1:
            eta_txt = "less than a minute left"
        elif eta < 90:
            eta_txt = f"about {int(round(eta))} min left"
        else:
            eta_txt = f"about {eta / 60:.1f} hours left"
        line = f"{mode}: {percent}% done | {done} of {total} {unit} | {eta_txt}"
        out = {"line": line, "percent": percent, "eta_min": None if eta is None else round(eta, 1)}
    os.makedirs("state", exist_ok=True)
    with open("state/progress.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh)
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
