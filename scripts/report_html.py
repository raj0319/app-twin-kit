"""Render docs/verify/report.md and docs/verify/gaps.md into one HTML page the
client can open or that Claude can publish as a shareable artifact.

Usage: python scripts/report_html.py [--out docs/verify/report.html]
"""
import argparse
import html
import os
import re
import sys
from datetime import datetime

CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--muted:#666;--ok:#1b7f3b;--bad:#b3261e;--warn:#9a6700;--line:#e5e5e5}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#121212;--fg:#eee;--muted:#aaa;--line:#333}}
body{margin:0;padding:24px 16px;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:960px;margin-inline:auto}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px}
.sub{color:var(--muted);margin-bottom:20px}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line)}
.PASS{color:var(--ok);font-weight:600}.FAIL{color:var(--bad);font-weight:600}
.gap{border:1px solid var(--line);border-radius:8px;padding:10px 12px;margin:8px 0}
.sev-blocks{border-left:4px solid var(--bad)}.sev-wrong{border-left:4px solid var(--warn)}.sev-cosmetic{border-left:4px solid var(--muted)}
.tiles{display:flex;gap:12px;flex-wrap:wrap;margin:12px 0}.tile{flex:1 1 120px;border:1px solid var(--line);border-radius:8px;padding:10px}
.tile b{font-size:22px;display:block}
"""


def read(path):
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def report_rows(text):
    rows = []
    for line in text.splitlines():
        if not line.startswith("|") or "---" in line or "PASS/FAIL" in line:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) >= 2 and cells[1] in ("PASS", "FAIL"):
            rows.append(cells)
    return rows


def gaps(text):
    out = []
    for block in re.split(r"\n(?=### Gap:)", text):
        if not block.startswith("### Gap:"):
            continue
        title = block.splitlines()[0][len("### Gap:"):].strip()
        get = lambda k: (re.search(rf"\*\*{k}:\*\*\s*(.*)", block) or [None, ""])[1].strip()
        out.append(
            {
                "title": title,
                "orig": get("Original did"),
                "new": get("New system did"),
                "sev": get("Severity"),
                "status": get("Status"),
            }
        )
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="docs/verify/report.html")
    args = ap.parse_args()

    rows = report_rows(read("docs/verify/report.md"))
    gl = gaps(read("docs/verify/gaps.md"))
    open_gaps = [g for g in gl if g["status"].startswith("open")]
    passed = sum(1 for r in rows if r[1] == "PASS")
    failed = sum(1 for r in rows if r[1] == "FAIL")

    e = html.escape
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<title>Twin Verify Report</title><style>", CSS, "</style></head><body>",
        "<h1>Twin verification report</h1>",
        f"<div class='sub'>Generated {datetime.now():%Y-%m-%d %H:%M}</div>",
        "<div class='tiles'>",
        f"<div class='tile'><b>{passed}</b>tasks pass</div>",
        f"<div class='tile'><b>{failed}</b>tasks fail</div>",
        f"<div class='tile'><b>{len(open_gaps)}</b>open gaps</div>",
        "</div><h2>Tasks</h2><table><tr><th>Task</th><th>Result</th><th>Date</th><th>Gaps</th></tr>",
    ]
    for r in rows:
        cells = (r + ["", "", ""])[:4]
        parts.append(
            f"<tr><td>{e(cells[0])}</td><td class='{cells[1]}'>{e(cells[1])}</td>"
            f"<td>{e(cells[2])}</td><td>{e(cells[3])}</td></tr>"
        )
    if not rows:
        parts.append("<tr><td colspan='4'>No tasks verified yet.</td></tr>")
    parts.append("</table><h2>Open gaps</h2>")
    if not open_gaps:
        parts.append("<p>None.</p>")
    for g in open_gaps:
        cls = "sev-blocks" if g["sev"].startswith("blocks") else "sev-wrong" if g["sev"].startswith("wrong") else "sev-cosmetic"
        parts.append(
            f"<div class='gap {cls}'><strong>{e(g['title'])}</strong> <span class='sub'>({e(g['sev'])})</span>"
            f"<br>Original: {e(g['orig'])}<br>New system: {e(g['new'])}</div>"
        )
    parts.append("</body></html>")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write("".join(parts))
    print(f"Wrote {args.out}: {passed} pass, {failed} fail, {len(open_gaps)} open gaps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
