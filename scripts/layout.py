"""Copy the original app's screen layout and check the twin against it.

The original's layout comes from the control tree in docs/raw/screens/<screen>.md
(written by ui_tree.py or exported by App Watcher): every control's type, name,
automation id and position. Only the layout is used: where each control sits and
how big it is. Colours, fonts, icons and logos are not read and not copied.

Usage:
  python scripts/layout.py extract docs/raw/screens/invoice.md --out docs/spec/layout/invoice.json
  python scripts/layout.py extract-all docs/raw/screens docs/spec/layout
  python scripts/layout.py compare <original.md|.json> <twin.md|.json> [--tol 6] [--out report.md] [--json]
  python scripts/layout.py js          # prints the browser snippet that dumps a web twin's layout as JSON

The twin side is either a .md made by ui_tree.py on the twin's window (desktop twin),
or the JSON printed by the `js` snippet run in the twin's page (web twin).

Controls are matched by id first (the twin gives each control the "id" from the
layout file), then by automation id, then by type and name. Before measuring, the
twin is shifted (and scaled, when the screen scaling differs) so window frames and
title bars do not count as differences.
"""
import argparse
import json
import os
import re
import statistics
import sys

# control types that make up a screen's layout; everything else (wrappers, scroll bars,
# rows inside grids, images and icons) is ignored
LAYOUT_TYPES = {
    "Button", "SplitButton", "Hyperlink", "MenuItem", "MenuBar", "ToolBar", "StatusBar",
    "Edit", "ComboBox", "Spinner", "Slider", "Calendar", "Document",
    "CheckBox", "RadioButton", "Text", "Group",
    "DataGrid", "Table", "List", "Tree", "Tab", "TabItem", "Header",
}
ROW_TYPES = {"DataItem", "ListItem", "TreeItem", "HeaderItem", "Row"}
SKIP_SUBTREE = {"ScrollBar", "TitleBar"}
FAMILY = {
    "Edit": "input", "ComboBox": "input", "Spinner": "input", "Document": "input", "Calendar": "input", "Slider": "input",
    "Button": "button", "SplitButton": "button", "Hyperlink": "button", "MenuItem": "button",
    "CheckBox": "check", "RadioButton": "check",
    "Text": "label", "Header": "label",
    "DataGrid": "grid", "Table": "grid", "List": "grid", "Tree": "grid",
    "Tab": "tab", "TabItem": "tabitem", "Group": "group",
    "MenuBar": "bar", "ToolBar": "bar", "StatusBar": "bar",
}
POS_RE = re.compile(r"(-?\d+)\s*,\s*(-?\d+)\s+(\d+)\s*x\s*(\d+)")


def slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:40]


def clean_name(name):
    return re.sub(r"[&:*]", "", name or "").strip().lower()


def meaningful_aid(aid):
    """Automation ids that are numbers, GUIDs or handles change between runs and builds."""
    if not aid:
        return False
    if re.fullmatch(r"[\d\-]+", aid) or re.fullmatch(r"[0-9a-fA-F\-]{24,}", aid):
        return False
    return True


def suggested_id(c):
    if meaningful_aid(c["aid"]):
        return c["aid"]
    base = slug(c["name"])
    return f"{slug(c['type'])}-{base}" if base else ""


# ---------------------------------------------------------------- reading

def read_md(path):
    """Rows of the control tree table: (depth, type, name, aid, x, y, w, h)."""
    rows, shot, in_table = [], None, False
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if s.lower().startswith("screenshot:"):
                v = s.split(":", 1)[1].strip()
                if v and not v.startswith("("):
                    shot = v
            if s.startswith("| Depth | Type | Name | AutomationId | Position"):
                in_table = True
                continue
            if in_table:
                if not s.startswith("|"):
                    in_table = False
                    continue
                if s.startswith("|---"):
                    continue
                cells = [c.strip() for c in s.strip("|").split("|")]
                if len(cells) < 5 or not cells[0].isdigit():
                    continue
                m = POS_RE.search(cells[4])
                x, y, w, h = (int(v) for v in m.groups()) if m else (0, 0, 0, 0)
                rows.append({"depth": int(cells[0]), "type": cells[1], "name": cells[2],
                             "aid": cells[3], "x": x, "y": y, "w": w, "h": h})
    return rows, shot


def layout_from_rows(rows):
    """Window size and the layout controls, positions relative to the window's top-left
    (below the title bar when the tree shows one)."""
    if not rows:
        return {"window": {"w": 0, "h": 0}, "controls": []}
    win = rows[0]
    ox, oy = win["x"], win["y"]
    bar = next((r for r in rows if r["type"] == "TitleBar" and r["h"] > 0), None)
    if bar:
        ox, oy = bar["x"], bar["y"] + bar["h"]
    controls, skip_below = [], None
    for r in rows[1:]:
        if skip_below is not None:
            if r["depth"] > skip_below:
                continue
            skip_below = None
        if r["type"] in ROW_TYPES or r["type"] in SKIP_SUBTREE:
            skip_below = r["depth"]
            continue
        if r["type"] not in LAYOUT_TYPES or r["w"] <= 0 or r["h"] <= 0:
            continue
        if not r["name"] and not meaningful_aid(r["aid"]):
            continue
        rx, ry = r["x"] - ox, r["y"] - oy
        if rx + r["w"] < 0 or ry + r["h"] < 0 or rx > win["w"] or ry > win["h"]:
            continue  # off screen (hidden tab pages, scrolled away)
        c = {"type": r["type"], "name": r["name"], "aid": r["aid"],
             "x": rx, "y": ry, "w": r["w"], "h": r["h"]}
        c["id"] = suggested_id(c)
        controls.append(c)
    return {"window": {"w": win["w"], "h": win["h"] - (oy - win["y"])}, "controls": controls}


def load(path):
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for c in data.get("controls", []):
            c.setdefault("aid", c.get("id", ""))
            c.setdefault("id", c.get("aid", ""))
            c.setdefault("name", "")
            c.setdefault("type", "")
        return data
    rows, shot = read_md(path)
    data = layout_from_rows(rows)
    data["screen"] = os.path.splitext(os.path.basename(path))[0]
    if shot:
        data["screenshot"] = os.path.normpath(os.path.join(os.path.dirname(path), shot)).replace("\\", "/")
    return data


# ---------------------------------------------------------------- compare

def match(old, new):
    pairs, used = [], set()

    def take(pred):
        for i, o in enumerate(old):
            if any(p[0] == i for p in pairs):
                continue
            for j, n in enumerate(new):
                if j not in used and pred(o, n):
                    pairs.append((i, j))
                    used.add(j)
                    break

    def eq(a, b):
        return bool(a) and bool(b) and a.lower() == b.lower()

    take(lambda o, n: eq(o.get("id"), n.get("id")) or eq(o.get("id"), n.get("aid")))
    take(lambda o, n: meaningful_aid(o["aid"]) and eq(o["aid"], n.get("aid")))
    take(lambda o, n: clean_name(o["name"]) and clean_name(o["name"]) == clean_name(n["name"])
         and FAMILY.get(o["type"], o["type"]) == FAMILY.get(n["type"], n["type"]))
    return pairs, used


def compare(old_l, new_l, tol):
    old, new = old_l["controls"], new_l["controls"]
    pairs, used = match(old, new)
    ratios = [new[j]["w"] / old[i]["w"] for i, j in pairs if old[i]["w"] >= 20 and new[j]["w"] > 0]
    scale = statistics.median(ratios) if len(ratios) >= 3 else 1.0
    if not 0.6 <= scale <= 1.6 or abs(scale - 1) < 0.05:
        scale = 1.0
    dxs = [new[j]["x"] - old[i]["x"] * scale for i, j in pairs]
    dys = [new[j]["y"] - old[i]["y"] * scale for i, j in pairs]
    shift = (statistics.median(dxs), statistics.median(dys)) if pairs else (0.0, 0.0)

    items, total = [], 0.0
    matched = dict(pairs)
    for i, o in enumerate(old):
        label = o["name"] or o["aid"] or o["id"]
        if i not in matched:
            items.append({"kind": "missing", "type": o["type"], "name": label, "id": o["id"],
                          "where": f"{o['x']},{o['y']} {o['w']}x{o['h']}"})
            continue
        n = new[matched[i]]
        dx = round(n["x"] - (o["x"] * scale + shift[0]))
        dy = round(n["y"] - (o["y"] * scale + shift[1]))
        dw = round(n["w"] - o["w"] * scale)
        dh = round(n["h"] - o["h"] * scale)
        err = max(abs(dx), abs(dy), abs(dw), abs(dh))
        total += 1.0 if err <= tol else 0.5 if err <= 3 * tol else 0.0
        if err > tol:
            kind = "moved" if max(abs(dx), abs(dy)) > tol else "resized"
            items.append({"kind": kind, "type": o["type"], "name": label, "id": o["id"],
                          "dx": dx, "dy": dy, "dw": dw, "dh": dh})
    extra = [{"kind": "extra", "type": n["type"], "name": n["name"] or n.get("id", ""), "id": n.get("id", "")}
             for j, n in enumerate(new) if j not in used]
    score = round(100 * total / len(old)) if old else 100
    return {
        "score": score,
        "original_controls": len(old),
        "matched": len(pairs),
        "window": {"original": old_l["window"], "twin": new_l.get("window", {})},
        "scale": round(scale, 3),
        "shift": [round(shift[0]), round(shift[1])],
        "differences": items,
        "extra": extra,
    }


def report_md(res, old_path, new_path):
    w = res["window"]
    out = [
        f"# Layout check: {os.path.basename(old_path)} vs {os.path.basename(new_path)}",
        "",
        f"**Layout match: {res['score']}%** ({res['matched']} of {res['original_controls']} controls found in the twin)",
        "",
        f"- Window: original {w['original'].get('w')}x{w['original'].get('h')}, twin {w['twin'].get('w')}x{w['twin'].get('h')}",
        f"- Twin scaled by {res['scale']} and shifted by {res['shift'][0]},{res['shift'][1]} px before measuring",
        "",
    ]
    if res["differences"]:
        out += ["| Control | Type | Problem | Fix |", "|---|---|---|---|"]
        for d in res["differences"]:
            if d["kind"] == "missing":
                out.append(f"| {d['name']} | {d['type']} | missing in twin | add it at {d['where']} (id `{d['id']}`) |")
            else:
                out.append(f"| {d['name']} | {d['type']} | {d['kind']} | move {d['dx']:+},{d['dy']:+} px, size {d['dw']:+}x{d['dh']:+} px off |")
        out.append("")
    if res["extra"]:
        out.append("Twin controls not in the original: " + ", ".join(f"{e['name']} ({e['type']})" for e in res["extra"][:30]))
        out.append("")
    if not res["differences"] and not res["extra"]:
        out.append("Same layout.")
    return "\n".join(out)


# ---------------------------------------------------------------- browser snippet

JS = r"""(() => {
  // Dumps the twin page's layout for scripts/layout.py compare. Every control carries data-aid.
  const root = document.querySelector('[data-screen]') || document.body;
  const r0 = root.getBoundingClientRect();
  const typeOf = el => {
    if (el.dataset.type) return el.dataset.type;
    const t = el.tagName.toLowerCase(), ty = (el.getAttribute('type') || '').toLowerCase();
    if (t === 'input' && ty === 'checkbox') return 'CheckBox';
    if (t === 'input' && ty === 'radio') return 'RadioButton';
    if (t === 'input' && (ty === 'button' || ty === 'submit')) return 'Button';
    if (t === 'input' || t === 'textarea') return 'Edit';
    if (t === 'select') return 'ComboBox';
    if (t === 'button') return 'Button';
    if (t === 'a') return 'Hyperlink';
    if (t === 'table') return 'DataGrid';
    if (t === 'fieldset') return 'Group';
    return 'Text';
  };
  const controls = [...root.querySelectorAll('[data-aid]')].map(el => {
    const b = el.getBoundingClientRect();
    const name = el.dataset.name || el.getAttribute('aria-label') || (el.labels && el.labels[0] && el.labels[0].innerText) || el.value || el.innerText || '';
    return { id: el.dataset.aid, aid: el.dataset.aid, type: typeOf(el), name: name.trim().slice(0, 120),
             x: Math.round(b.left - r0.left), y: Math.round(b.top - r0.top), w: Math.round(b.width), h: Math.round(b.height) };
  }).filter(c => c.w > 0 && c.h > 0);
  return JSON.stringify({ screen: root.dataset.screen || document.title, window: { w: Math.round(r0.width), h: Math.round(r0.height) }, controls });
})()"""


# ---------------------------------------------------------------- commands

def write_json(data, out):
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract", help="one screen record -> layout JSON")
    e.add_argument("screen")
    e.add_argument("--out")
    a = sub.add_parser("extract-all", help="every screen record in a folder -> layout JSON files")
    a.add_argument("screens_dir")
    a.add_argument("out_dir")
    c = sub.add_parser("compare", help="original vs twin layout")
    c.add_argument("original")
    c.add_argument("twin")
    c.add_argument("--tol", type=int, default=6, help="pixels a control may be off (default 6)")
    c.add_argument("--out", help="write the Markdown report here")
    c.add_argument("--json", action="store_true", help="print the result as JSON")
    sub.add_parser("js", help="print the browser snippet for a web twin")
    args = p.parse_args()

    if args.cmd == "js":
        print(JS)
        return 0
    if args.cmd == "extract":
        data = load(args.screen)
        if args.out:
            write_json(data, args.out)
            print(f"Wrote {len(data['controls'])} controls to {args.out}")
        else:
            print(json.dumps(data, indent=1, ensure_ascii=False))
        return 0
    if args.cmd == "extract-all":
        n = 0
        for f in sorted(os.listdir(args.screens_dir)):
            if not f.lower().endswith(".md"):
                continue
            data = load(os.path.join(args.screens_dir, f))
            if not data["controls"]:
                print(f"skipped {f}: no control positions")
                continue
            write_json(data, os.path.join(args.out_dir, os.path.splitext(f)[0] + ".json"))
            n += 1
        print(f"Wrote {n} layout files to {args.out_dir}")
        return 0
    old_l, new_l = load(args.original), load(args.twin)
    res = compare(old_l, new_l, args.tol)
    if args.json:
        print(json.dumps(res, indent=1, ensure_ascii=False))
    else:
        text = report_md(res, args.original, args.twin)
        if args.out:
            os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
            with open(args.out, "w", encoding="utf-8") as fh:
                fh.write(text + "\n")
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
