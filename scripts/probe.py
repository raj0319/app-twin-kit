"""Type a value into a field of the original app, optionally press Enter, and
record what the screen shows back: result rows, messages, dialogs.

Usage:
  python scripts/probe.py --title "Customers" --field "Search" --value "abc" --enter \
      --out docs/raw/probes/customers-search.md

  --field   part of the field's label or its AutomationId
  --read    control type to read results from (default: DataGrid, List, Table, Tree)
  --clear   clear the field afterwards (default on)

Safe use: only on search, filter, sort and lookup fields, or on form fields
when you press Cancel afterwards. Never on a screen where Enter means Save.
"""
import argparse
import os
import sys
import time
from datetime import datetime

RESULT_TYPES = ("DataGrid", "List", "Table", "Tree")


def find_field(win, key):
    key_l = key.lower()
    for ctrl in win.descendants():
        info = ctrl.element_info
        if info.control_type not in ("Edit", "ComboBox", "Document"):
            continue
        name = (info.name or "").lower()
        auto = (info.automation_id or "").lower()
        if key_l in name or key_l in auto:
            return ctrl
    # fall back: label next to an edit box
    for ctrl in win.descendants(control_type="Text"):
        if key_l in (ctrl.element_info.name or "").lower():
            try:
                sib = ctrl.parent().children(control_type="Edit")
                if sib:
                    return sib[0]
            except Exception:
                pass
    return None


def read_results(win, types, limit=40):
    rows = []
    for t in types:
        for grid in win.descendants(control_type=t):
            items = grid.descendants()
            texts = []
            for it in items:
                n = (it.element_info.name or "").strip()
                ct = it.element_info.control_type
                if n and ct in ("DataItem", "ListItem", "TreeItem", "Text", "Custom"):
                    texts.append(n.replace("|", "/"))
            if texts:
                rows.append((t, texts[:limit], len(texts)))
    return rows


def read_messages(app_pid, before_handles):
    from pywinauto import Desktop

    msgs = []
    for w in Desktop(backend="uia").windows():
        try:
            if w.process_id() != app_pid or w.handle in before_handles:
                continue
            texts = [c.window_text() for c in w.descendants(control_type="Text") if c.window_text()]
            msgs.append((w.window_text(), " / ".join(texts)[:300]))
        except Exception:
            continue
    return msgs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True)
    ap.add_argument("--field", required=True)
    ap.add_argument("--value", required=True)
    ap.add_argument("--enter", action="store_true")
    ap.add_argument("--read", nargs="*", default=list(RESULT_TYPES))
    ap.add_argument("--wait", type=float, default=1.5)
    ap.add_argument("--no-clear", action="store_true")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    try:
        from pywinauto import Desktop
    except ImportError:
        print("pywinauto not installed. Run: pip install -r scripts/requirements.txt")
        return 1

    win = Desktop(backend="uia").window(title_re=f".*{args.title}.*")
    win.wait("exists", timeout=5)
    pid = win.process_id()
    before = {w.handle for w in Desktop(backend="uia").windows() if w.process_id() == pid}

    field = find_field(win, args.field)
    if field is None:
        print(f"Field '{args.field}' not found on '{win.window_text()}'.")
        return 2

    try:
        field.set_focus()
        field.type_keys("^a{BACKSPACE}", set_foreground=True)
        field.type_keys(args.value, with_spaces=True, set_foreground=True)
        if args.enter:
            field.type_keys("{ENTER}", set_foreground=True)
    except Exception as exc:
        print(f"Could not type into field: {exc}")
        return 3
    time.sleep(args.wait)

    results = read_results(win, args.read)
    messages = read_messages(pid, before)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    new = not os.path.exists(args.out)
    with open(args.out, "a", encoding="utf-8") as fh:
        if new:
            fh.write(f"# Probes: {win.window_text()}\n\n")
        fh.write(f"## {datetime.now():%H:%M} field `{args.field}` = `{args.value}`"
                 f"{' + Enter' if args.enter else ''}\n\n")
        if not results and not messages:
            fh.write("No visible result or message.\n\n")
        for t, texts, total in results:
            fh.write(f"- {t}: {total} items. First: " + " | ".join(texts[:12]) + "\n")
        for title, body in messages:
            fh.write(f"- Dialog `{title}`: {body}\n")
        fh.write("\n")

    # close any dialog we caused, then clear the field
    for w in Desktop(backend="uia").windows():
        try:
            if w.process_id() == pid and w.handle not in before:
                w.type_keys("{ESC}")
        except Exception:
            pass
    if not args.no_clear:
        try:
            field.set_focus()
            field.type_keys("^a{BACKSPACE}")
        except Exception:
            pass

    print(f"Probe recorded to {args.out}: {sum(r[2] for r in results)} result items, {len(messages)} messages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
