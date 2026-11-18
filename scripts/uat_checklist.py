"""Build a user acceptance checklist from the spec: one row per task, for a
real user to try on the twin and tick yes or no.

  python scripts/uat_checklist.py

Writes docs/verify/uat-checklist.md and docs/verify/uat-checklist.html.
"""
import glob
import html
import os
import re
import sys
from datetime import datetime


def first_line(text, key):
    m = re.search(rf"\*\*{key}:\*\*\s*(.*)", text)
    return m.group(1).strip() if m else ""


def steps(text):
    out = []
    for line in text.splitlines():
        m = re.match(r"\s*(\d+)[.)]\s+(.*)", line)
        if m:
            out.append(m.group(2).strip())
    return out


def main():
    tasks = []
    for path in sorted(glob.glob("docs/spec/*.md")):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        raw_title = (re.search(r"^#\s+(.*)", text, re.M) or [None, os.path.basename(path)])[1]
        if raw_title.lower().startswith("screen") or "/screen-" in path.replace("\\", "/"):
            continue
        title = re.sub(r"^Task:\s*", "", raw_title).strip()
        tasks.append(
            {
                "title": title,
                "who": first_line(text, "Who does it"),
                "goal": first_line(text, "Goal"),
                "steps": steps(text)[:6],
                "file": path.replace("\\", "/"),
            }
        )

    stamp = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("docs/verify", exist_ok=True)

    md = [
        "# User acceptance checklist",
        "",
        f"Generated {stamp}. Try each task on the NEW system, the way you do it today.",
        "Tick Works, or write what was different.",
        "",
        "| # | Task | Who | Tried by | Works? | What was different |",
        "|---|---|---|---|---|---|",
    ]
    for i, t in enumerate(tasks, 1):
        md.append(f"| {i} | {t['title']} | {t['who']} |  | yes / no |  |")
    md += ["", "## Steps for each task", ""]
    for i, t in enumerate(tasks, 1):
        md.append(f"### {i}. {t['title']}")
        if t["goal"]:
            md.append(f"Goal: {t['goal']}")
        for s in t["steps"]:
            md.append(f"- {s}")
        md.append("")
    with open("docs/verify/uat-checklist.md", "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))

    e = html.escape
    rows = "".join(
        f"<tr><td>{i}</td><td><b>{e(t['title'])}</b><br><small>{e(t['goal'])}</small>"
        f"<ul>{''.join(f'<li>{e(s)}</li>' for s in t['steps'])}</ul></td>"
        f"<td>{e(t['who'])}</td><td><input></td>"
        f"<td><label><input type=checkbox> yes</label> <label><input type=checkbox> no</label></td>"
        f"<td><textarea rows=2></textarea></td></tr>"
        for i, t in enumerate(tasks, 1)
    )
    page = f"""<!doctype html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'><title>Acceptance Checklist</title>
<style>
:root{{--bg:#fff;--fg:#1a1a1a;--line:#e5e5e5;--muted:#666}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#121212;--fg:#eee;--line:#333;--muted:#aaa}}}}
body{{margin:0;padding:24px 16px;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:1000px;margin-inline:auto}}
table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{vertical-align:top;text-align:left;padding:8px;border-bottom:1px solid var(--line)}}
ul{{margin:4px 0 0 16px;padding:0;color:var(--muted)}}input,textarea{{width:100%;box-sizing:border-box}}
@media print{{input,textarea{{border:1px solid #999}}}}
</style></head><body>
<h1>User acceptance checklist</h1>
<p>Generated {stamp}. Try each task on the new system the way you do it today. Print this page or fill it in and save.</p>
<table><tr><th>#</th><th>Task</th><th>Who</th><th>Tried by</th><th>Works?</th><th>What was different</th></tr>{rows}</table>
</body></html>"""
    with open("docs/verify/uat-checklist.html", "w", encoding="utf-8") as fh:
        fh.write(page)
    print(f"Wrote docs/verify/uat-checklist.md and .html with {len(tasks)} tasks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
