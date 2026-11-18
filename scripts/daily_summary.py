"""One-page summary of a day's work, for a client who checks in once a day.

  python scripts/daily_summary.py [--date YYYY-MM-DD]

Writes docs/summary/<date>.md and docs/summary/latest.html (same content,
publishable as an artifact and updated in place each run).
"""
import argparse
import glob
import html
import json
import os
import re
import sys
from datetime import date


def read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return ""


def load_json(path, default):
    try:
        return json.loads(read(path))
    except Exception:
        return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    args = ap.parse_args()
    day = args.date

    mode = load_json("state/mode.json", {}).get("mode", "not started")
    progress = load_json("state/progress.json", {}).get("line", "")
    project = load_json("state/project.json", {})
    app = project.get("app_name", "the app")

    log = [l for l in read("state/progress.md").splitlines() if l.startswith(f"- {day}")]
    touched = {}
    for l in log:
        m = re.search(r": (\S+)$", l)
        if m:
            p = m.group(1)
            area = p.split("/")[1] if p.startswith("docs/") and "/" in p[5:] else p.split("/")[0]
            touched[area] = touched.get(area, 0) + 1
    notes = [l[2:] for l in log if not re.search(r"(Write|Edit|MultiEdit): ", l)]

    screens = len(glob.glob("docs/raw/screens/*.md"))
    probes = len(glob.glob("docs/raw/probes/*.md"))
    tasks = len(glob.glob("docs/raw/tasks/*.md"))
    spec = len(glob.glob("docs/spec/*.md"))
    gaps_text = read("docs/verify/gaps.md")
    open_gaps = gaps_text.count("**Status:** open")
    blocks = len(re.findall(r"\*\*Severity:\*\*\s*blocks work[\s\S]*?\*\*Status:\*\*\s*open", gaps_text))
    report = read("docs/verify/report.md")
    passed = report.count("| PASS |")
    failed = report.count("| FAIL |")
    decisions = [l for l in read("docs/decisions.md").splitlines() if l.startswith("## ")][-3:]

    lines = [
        f"# Daily summary, {day}",
        "",
        f"Twin of **{app}**. Mode now: **{mode}**.",
        progress and f"Progress: {progress}" or "",
        "",
        "## What happened today",
    ]
    if touched:
        for area, n in sorted(touched.items(), key=lambda x: -x[1]):
            lines.append(f"- {n} files updated in {area}")
    else:
        lines.append("- No files changed today.")
    for n in notes[-8:]:
        lines.append(f"- {n}")
    lines += [
        "",
        "## Where things stand",
        f"- Screens recorded: {screens}, probed: {probes}",
        f"- Tasks recorded: {tasks}, in spec: {spec}",
        f"- Verified: {passed} pass, {failed} fail",
        f"- Open gaps: {open_gaps} (blocking: {blocks})",
    ]
    if decisions:
        lines += ["", "## Latest decisions"] + [f"- {d[3:]}" for d in decisions]
    lines += ["", "## Next", f"- Continue in {mode} mode. Type /progress for the live line."]
    md = "\n".join(l for l in lines if l is not None)

    os.makedirs("docs/summary", exist_ok=True)
    with open(f"docs/summary/{day}.md", "w", encoding="utf-8") as fh:
        fh.write(md + "\n")

    body, in_list = [], False
    for l in md.splitlines():
        is_item = l.startswith("- ")
        if in_list and not is_item:
            body.append("</ul>")
            in_list = False
        if l.startswith("# "):
            body.append(f"<h1>{html.escape(l[2:])}</h1>")
        elif l.startswith("## "):
            body.append(f"<h2>{html.escape(l[3:])}</h2>")
        elif is_item:
            if not in_list:
                body.append("<ul>")
                in_list = True
            body.append(f"<li>{html.escape(l[2:])}</li>")
        elif l.strip():
            body.append(f"<p>{html.escape(l.replace('**', ''))}</p>")
    if in_list:
        body.append("</ul>")
    page = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'><title>Twin Daily Summary</title>"
        "<style>:root{--bg:#fff;--fg:#1a1a1a;--muted:#666}"
        "@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#121212;--fg:#eee;--muted:#aaa}}"
        "body{margin:0;padding:24px 16px;background:var(--bg);color:var(--fg);font:16px/1.6 system-ui,sans-serif;max-width:760px;margin-inline:auto}"
        "h1{font-size:24px}h2{font-size:18px;margin-top:24px}li{margin:4px 0}</style></head><body>"
        + "".join(body)
        + "</body></html>"
    )
    with open("docs/summary/latest.html", "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"Wrote docs/summary/{day}.md and docs/summary/latest.html")
    return 0


if __name__ == "__main__":
    sys.exit(main())
