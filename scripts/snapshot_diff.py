"""Snapshot data files and SQLite databases, then diff two snapshots.

Usage:
  python scripts/snapshot_diff.py snapshot <name> --paths <file-or-folder> [...]
  python scripts/snapshot_diff.py diff <name-before> <name-after>

Snapshots are written to state/snapshots/<name>.json (not committed).
SQLite files are opened read only and every table is dumped.
Other files are recorded by size and hash. Folders are walked.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import sys

SNAP_DIR = os.path.join("state", "snapshots")
SQLITE_MAGIC = b"SQLite format 3\x00"


def is_sqlite(path):
    try:
        with open(path, "rb") as fh:
            return fh.read(16) == SQLITE_MAGIC
    except OSError:
        return False


def dump_sqlite(path):
    uri = f"file:{os.path.abspath(path)}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    tables = {}
    try:
        names = [
            r[0]
            for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        for name in names:
            cols = [c[1] for c in con.execute(f'PRAGMA table_info("{name}")')]
            pk = [c[1] for c in con.execute(f'PRAGMA table_info("{name}")') if c[5]]
            rows = {}
            for i, row in enumerate(con.execute(f'SELECT * FROM "{name}"')):
                rec = {c: row[c] for c in cols}
                key = "|".join(str(rec[c]) for c in pk) if pk else hashlib.md5(
                    json.dumps(rec, sort_keys=True, default=str).encode()
                ).hexdigest()
                rows[key] = rec
            tables[name] = {"columns": cols, "rows": rows}
    finally:
        con.close()
    return tables


def file_entry(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return {"size": os.path.getsize(path), "sha256": h.hexdigest()}


def snapshot(name, paths):
    data = {"sqlite": {}, "files": {}}
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in files:
                    full = os.path.join(root, f)
                    if is_sqlite(full):
                        data["sqlite"][full] = dump_sqlite(full)
                    else:
                        data["files"][full] = file_entry(full)
        elif os.path.isfile(p):
            if is_sqlite(p):
                data["sqlite"][p] = dump_sqlite(p)
            else:
                data["files"][p] = file_entry(p)
        else:
            print(f"warning: path not found: {p}")
    os.makedirs(SNAP_DIR, exist_ok=True)
    out = os.path.join(SNAP_DIR, f"{name}.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, default=str)
    print(f"Snapshot saved: {out} ({len(data['sqlite'])} db, {len(data['files'])} files)")


def load(name):
    with open(os.path.join(SNAP_DIR, f"{name}.json"), encoding="utf-8") as fh:
        return json.load(fh)


def diff(before, after):
    a, b = load(before), load(after)
    changes = 0
    print(f"## Data changes: {before} -> {after}\n")
    for db in sorted(set(a["sqlite"]) | set(b["sqlite"])):
        ta, tb = a["sqlite"].get(db, {}), b["sqlite"].get(db, {})
        for t in sorted(set(ta) | set(tb)):
            ra, rb = ta.get(t, {}).get("rows", {}), tb.get(t, {}).get("rows", {})
            added = [k for k in rb if k not in ra]
            removed = [k for k in ra if k not in rb]
            changed = [k for k in rb if k in ra and ra[k] != rb[k]]
            if not (added or removed or changed):
                continue
            changes += 1
            print(f"### {os.path.basename(db)} / {t}: +{len(added)} -{len(removed)} ~{len(changed)}")
            for k in added[:20]:
                print(f"- added {k}: {json.dumps(rb[k], default=str)}")
            for k in removed[:20]:
                print(f"- removed {k}: {json.dumps(ra[k], default=str)}")
            for k in changed[:20]:
                fields = {c: (ra[k][c], rb[k][c]) for c in rb[k] if ra[k].get(c) != rb[k].get(c)}
                print(f"- changed {k}: {json.dumps(fields, default=str)}")
            print()
    for f in sorted(set(a["files"]) | set(b["files"])):
        fa, fb = a["files"].get(f), b["files"].get(f)
        if fa == fb:
            continue
        changes += 1
        state = "created" if fa is None else "deleted" if fb is None else "modified"
        print(f"- file {state}: {f}")
    if changes == 0:
        print("No data changes detected.")


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("name")
    s.add_argument("--paths", nargs="+", required=True)
    d = sub.add_parser("diff")
    d.add_argument("before")
    d.add_argument("after")
    args = parser.parse_args()
    if args.cmd == "snapshot":
        snapshot(args.name, args.paths)
    else:
        diff(args.before, args.after)
    return 0


if __name__ == "__main__":
    sys.exit(main())
