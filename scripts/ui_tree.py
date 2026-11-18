"""Dump a Windows app's UI Automation control tree to Markdown and save a screenshot.

Usage:
  python scripts/ui_tree.py --list
  python scripts/ui_tree.py --title "Invoice" --out docs/raw/screens/invoice.md [--depth 8]

Needs: pip install -r scripts/requirements.txt
Read only: this script never clicks or types.
"""
import argparse
import os
import sys
from datetime import datetime


def list_windows():
    from pywinauto import Desktop

    print("| Title | Process | Class |")
    print("|---|---|---|")
    for w in Desktop(backend="uia").windows():
        try:
            title = w.window_text().strip()
            if not title:
                continue
            print(f"| {title} | {w.process_id()} | {w.class_name()} |")
        except Exception:
            continue


def walk(elem, depth, max_depth, rows):
    if depth > max_depth:
        return
    try:
        info = elem.element_info
        rect = info.rectangle
        rows.append(
            (
                depth,
                info.control_type or "",
                (info.name or "").replace("|", "/").strip(),
                info.automation_id or "",
                f"{rect.left},{rect.top} {rect.width()}x{rect.height()}",
            )
        )
    except Exception:
        return
    try:
        children = elem.children()
    except Exception:
        children = []
    for child in children:
        walk(child, depth + 1, max_depth, rows)


def dump(title, out_path, max_depth):
    from pywinauto import Desktop

    desktop = Desktop(backend="uia")
    win = desktop.window(title_re=f".*{title}.*")
    win.wait("exists", timeout=5)
    rows = []
    walk(win, 0, max_depth, rows)

    out_dir = os.path.dirname(out_path) or "."
    os.makedirs(out_dir, exist_ok=True)
    png_path = os.path.splitext(out_path)[0] + ".png"
    try:
        win.capture_as_image().save(png_path)
        shot = os.path.basename(png_path)
    except Exception as exc:  # window may be minimised or off screen
        shot = f"(screenshot failed: {exc})"

    template = os.path.join("docs", "templates", "screen.md")
    header = ""
    if os.path.exists(template):
        with open(template, encoding="utf-8") as fh:
            header = fh.read()

    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(header)
        fh.write("\n\n## Control tree (auto-generated)\n\n")
        fh.write(f"Window: {win.window_text()}  \n")
        fh.write(f"Captured: {datetime.now():%Y-%m-%d %H:%M}  \n")
        fh.write(f"Screenshot: {shot}\n\n")
        fh.write("| Depth | Type | Name | AutomationId | Position |\n")
        fh.write("|---|---|---|---|---|\n")
        for d, t, n, a, p in rows:
            fh.write(f"| {d} | {t} | {n} | {a} | {p} |\n")
    print(f"Wrote {len(rows)} controls to {out_path}")
    if len(rows) < 5:
        print(
            "Very few controls found. This app may not expose UI Automation. "
            "Fall back to the screenshot and the vision steps in the observe-app skill."
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="list top-level windows")
    parser.add_argument("--title", help="part of the window title")
    parser.add_argument("--out", help="output .md path")
    parser.add_argument("--depth", type=int, default=10)
    args = parser.parse_args()

    try:
        import pywinauto  # noqa: F401
    except ImportError:
        print("pywinauto not installed. Run: pip install -r scripts/requirements.txt")
        return 1

    if args.list:
        list_windows()
        return 0
    if not (args.title and args.out):
        parser.print_help()
        return 1
    dump(args.title, args.out, args.depth)
    return 0


if __name__ == "__main__":
    sys.exit(main())
