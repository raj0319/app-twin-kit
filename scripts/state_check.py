"""State-by-state verification (improvement #5).

Turns what App Watcher recorded about a screen into an expectation, then checks the twin against it
field by field, action by action, grid column by grid column, so VERIFY mode gets a measurable
"same as the original" score per screen, not only per task.

  python scripts/state_check.py expect docs/raw <screen title> [--out docs/spec/states/<screen>.json]
  python scripts/state_check.py expect-all docs/raw docs/spec/states
  python scripts/state_check.py check docs/spec/states/<screen>.json <twin dump .md|.json> [--out docs/verify/state/<screen>.md] [--json]

The expectation comes from docs/raw/screens/<screen>.md (fields, actions, shortcuts) and
docs/raw/probes/<screen>.md (suggestion lists, results after actions, validation rules), both written
by App Watcher's export. The twin dump is a ui_tree.py .md of the twin window, or the JSON printed by
`scripts/layout.py js` run in a web twin. Only presence and labels are compared, never colours or pixels.
"""
import argparse
import glob
import json
import os
import re
import sys

FIELD_TYPES = {"Edit", "ComboBox", "CheckBox", "RadioButton", "Spinner", "Slider", "Calendar", "Document", "DataGrid", "List", "Tree", "Table"}
ACTION_TYPES = {"Button", "MenuItem", "SplitButton", "Hyperlink", "TabItem"}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def parse_tree(path):
    """Reads a control-tree table (ui_tree.py / App Watcher screen record) into rows."""
    rows, in_tree = [], False
    for line in open(path, encoding="utf-8"):
        t = line.rstrip()
        if t.startswith("## Control tree") or t.startswith("| Depth"):
            in_tree = True
            continue
        if in_tree and t.startswith("|") and not t.startswith("|---"):
            c = [x.strip() for x in t.split("|")]
            if len(c) >= 6 and c[1].isdigit():
                rows.append({"depth": int(c[1]), "type": c[2], "name": c[3], "aid": c[4], "pos": c[5]})
    return rows


def tree_to_json(path):
    """A web twin's layout JSON (from layout.py js): list of {type,name,id,...}."""
    data = json.load(open(path, encoding="utf-8"))
    if isinstance(data, dict) and "controls" in data:
        data = data["controls"]
    return [{"depth": 0, "type": c.get("type", ""), "name": c.get("name") or c.get("label") or "", "aid": c.get("id") or c.get("automationId") or "", "pos": ""} for c in data]


def load_dump(path):
    return tree_to_json(path) if path.endswith(".json") else parse_tree(path)


def labels(rows, types):
    out = []
    for r in rows:
        if r["type"] in types:
            name = r["name"] or r["aid"]
            if name and not name.startswith("..."):
                out.append(name)
    return out


# ---------- expect ----------

def read_screen(raw, title):
    path = _find(os.path.join(raw, "screens"), title)
    fields, actions, shortcuts = [], [], {}
    if path:
        rows = parse_tree(path)
        # App Watcher's Fields/Actions tables carry the clean labels; fall back to the tree
        for sec, store in (("## Fields", "f"), ("## Actions", "a")):
            pass
        fields = _unique(labels(rows, FIELD_TYPES) + _table_col(path, "## Fields", 0))
        actions = _unique(labels(rows, ACTION_TYPES) + _table_col(path, "## Actions", 0))
        for name, key in _action_shortcuts(path):
            if key:
                shortcuts[name] = key
    return {"fields": fields, "actions": actions, "shortcuts": shortcuts}


def read_probe(raw, title):
    path = _find(os.path.join(raw, "probes"), title)
    lookups, results, validations = {}, {}, []
    if not path:
        return lookups, results, validations
    for line in open(path, encoding="utf-8"):
        t = line.strip()
        m = re.search(r"Suggestion list while typing: seen (\d+).*?up to (\d+) items", t)
        if m:
            fld = _prev_field
        m2 = re.match(r"## Field: (.+)", t)
        if m2:
            _set_prev(m2.group(1).strip())
        if m:
            lookups[_prev_field] = {"maxItems": int(m.group(2))}
        r = re.match(r"- After (.+?): grid columns (.+?);", t)
        if r:
            results[r.group(1).strip()] = {"columns": [c.strip() for c in r.group(2).split(",") if c.strip()]}
        v = re.match(r"- Validation: field `(.+?)` rejects (.+?) with message \"(.+?)\"", t)
        if v:
            validations.append({"field": v.group(1), "pattern": v.group(2), "message": v.group(3)})
    return lookups, results, validations


_prev_field = ""
def _set_prev(f):
    global _prev_field
    _prev_field = f


def expect(raw, title):
    sc = read_screen(raw, title)
    lookups, results, validations = read_probe(raw, title)
    return {"screen": title, **sc, "lookups": lookups, "results": results, "validations": validations}


# ---------- check ----------

def present(expected, actual):
    """For each expected label, is there an actual control with a matching (normalized, substring-either-way) name?"""
    acts = [norm(a) for a in actual]
    hits, misses = [], []
    for e in expected:
        ne = norm(e)
        if ne and any(ne == a or (len(ne) >= 4 and (ne in a or a in ne)) for a in acts):
            hits.append(e)
        else:
            misses.append(e)
    return hits, misses


def check(expect_path, dump_path):
    exp = json.load(open(expect_path, encoding="utf-8"))
    rows = load_dump(dump_path)
    tfields = labels(rows, FIELD_TYPES)
    tactions = labels(rows, ACTION_TYPES)
    ttext = [r["name"] for r in rows]
    fh, fm = present(exp.get("fields", []), tfields + ttext)
    ah, am = present(exp.get("actions", []), tactions + ttext)
    # grid columns expected after the actions on this screen
    cols_exp = _unique([c for r in exp.get("results", {}).values() for c in r.get("columns", [])])
    ch, cm = present(cols_exp, ttext)
    parts = []
    for name, h, m in (("fields", fh, fm), ("actions", ah, am), ("grid columns", ch, cm)):
        tot = len(h) + len(m)
        if tot:
            parts.append((name, len(h), tot, m))
    score = 0 if not parts else round(100.0 * sum(h for _, h, _, _ in parts) / sum(t for _, _, t, _ in parts))
    return exp, parts, score


def report(exp, parts, score):
    out = [f"# State check: {exp['screen']}", "", f"**Match: {score}%** (presence of fields, actions and grid columns; look and colours are not compared).", ""]
    out.append("| What | Found | Expected | Missing |")
    out.append("|---|---|---|---|")
    for name, h, t, miss in parts:
        out.append(f"| {name} | {h} | {t} | {', '.join(miss) if miss else '-'} |")
    if exp.get("shortcuts"):
        out += ["", "Keyboard shortcuts the twin should keep: " + ", ".join(f"{k} {a}" for a, k in exp["shortcuts"].items())]
    if exp.get("validations"):
        out += ["", "## Validation rules to test by hand or in a flow run"]
        for v in exp["validations"]:
            out.append(f"- field {v['field']}: {v['pattern']} should give \"{v['message']}\"")
    if exp.get("results"):
        out += ["", "## Grids to check after a search/open (same columns, same rows for a ZZTEST query)"]
        for a, r in exp["results"].items():
            out.append(f"- after {a}: columns {', '.join(r.get('columns', []))}")
    return "\n".join(out) + "\n"


# ---------- small helpers ----------

def _find(folder, title):
    if not os.path.isdir(folder):
        return None
    want = norm(title)
    best = None
    for f in glob.glob(os.path.join(folder, "*.md")):
        if f.lower().endswith((".live.md", ".watcher.md")):
            continue  # side files of the App Watcher vs live-app check
        if norm(os.path.splitext(os.path.basename(f))[0]) == want:
            return f
        # title may be collapsed ("Invoice #"): match the file whose first heading matches
        head = open(f, encoding="utf-8").readline()
        if norm(head).find(want) >= 0 or want.find(norm(head.replace("# Screen:", "").replace("# Probes:", ""))) >= 0:
            best = best or f
    return best


def _table_col(path, header, col):
    out, in_sec = [], False
    for line in open(path, encoding="utf-8"):
        t = line.rstrip()
        if t.startswith(header):
            in_sec = True
            continue
        if in_sec and t.startswith("## "):
            break
        if in_sec and t.startswith("|") and not t.startswith("|---") and not t.startswith("| Label") and not t.startswith("| Button"):
            cells = [x.strip() for x in t.split("|")]
            if len(cells) > col + 1 and cells[col + 1] and cells[col + 1] != "(no input fields seen)":
                out.append(cells[col + 1])
    return out


def _action_shortcuts(path):
    out, in_sec = [], False
    for line in open(path, encoding="utf-8"):
        t = line.rstrip()
        if t.startswith("## Actions"):
            in_sec = True
            continue
        if in_sec and t.startswith("## "):
            break
        if in_sec and t.startswith("|") and not t.startswith("|---") and not t.startswith("| Button"):
            c = [x.strip() for x in t.split("|")]
            if len(c) >= 7:
                out.append((c[1], c[5]))
    return out


def _unique(xs):
    seen, out = set(), []
    for x in xs:
        if x and norm(x) not in seen:
            seen.add(norm(x))
            out.append(x)
    return out


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("expect"); e.add_argument("raw"); e.add_argument("title"); e.add_argument("--out")
    ea = sub.add_parser("expect-all"); ea.add_argument("raw"); ea.add_argument("outdir")
    c = sub.add_parser("check"); c.add_argument("expect"); c.add_argument("dump"); c.add_argument("--out"); c.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.cmd == "expect":
        data = expect(a.raw, a.title)
        _write_json(a.out, data)
        print(("Wrote " + a.out) if a.out else json.dumps(data, indent=2))
    elif a.cmd == "expect-all":
        os.makedirs(a.outdir, exist_ok=True)
        n = 0
        for f in glob.glob(os.path.join(a.raw, "screens", "*.md")):
            if f.lower().endswith((".live.md", ".watcher.md")):
                continue
            title = open(f, encoding="utf-8").readline().replace("# Screen:", "").strip() or os.path.splitext(os.path.basename(f))[0]
            out = os.path.join(a.outdir, os.path.basename(f).replace(".md", ".json"))
            _write_json(out, expect(a.raw, title))
            n += 1
        print(f"Wrote {n} expectation files to {a.outdir}")
    elif a.cmd == "check":
        exp, parts, score = check(a.expect, a.dump)
        if a.json:
            print(json.dumps({"screen": exp["screen"], "score": score, "parts": [{"what": n, "found": h, "expected": t, "missing": m} for n, h, t, m in parts]}, indent=2))
        else:
            text = report(exp, parts, score)
            if a.out:
                os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
                open(a.out, "w", encoding="utf-8").write(text)
            print(f"{exp['screen']}: {score}% (report {a.out})" if a.out else text)
    return 0


def _write_json(path, data):
    if path:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        json.dump(data, open(path, "w", encoding="utf-8"), indent=2)


if __name__ == "__main__":
    sys.exit(main())
