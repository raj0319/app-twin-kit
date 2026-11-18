"""A fixed set of clearly-marked test values, shared by every agent.

  python scripts/testdata.py generate --entities customer item invoice
  python scripts/testdata.py show
  python scripts/testdata.py show customer

Writes state/testdata.json. Every value starts with ZZTEST so it is easy to
find and remove later, and so nobody mistakes it for real data.

The original app's database is never written by this kit. Test records are
created in the original app through its own screens (the recorder does this
as a task), and in the twin through its seed. Both sides then hold the same
records, which is what VERIFY needs.
"""
import argparse
import json
import os
import sys
from datetime import date, timedelta

PATH = os.path.join("state", "testdata.json")
TAG = "ZZTEST"


def make(entity, n):
    today = date.today()
    rows = []
    for i in range(1, n + 1):
        base = {
            "tag": TAG,
            "code": f"{TAG}-{entity[:3].upper()}-{i:03d}",
            "name": f"{TAG} {entity.title()} {i:03d}",
            "email": f"{TAG.lower()}.{entity}{i:03d}@example.invalid",
            "phone": f"+1 555 010 {i:04d}",
            "address": f"{i} Test Street, Testville",
            "date": (today - timedelta(days=i)).isoformat(),
            "quantity": i,
            "amount": round(100.0 * i + 0.5 * i, 2),
            "note": f"{TAG} record {i}, safe to delete",
        }
        rows.append(base)
    return rows


def generate(entities, count):
    data = {"tag": TAG, "entities": {e: make(e, count) for e in entities}}
    os.makedirs("state", exist_ok=True)
    with open(PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1)
    print(f"Wrote {PATH}: {', '.join(f'{e} x{count}' for e in entities)}")


def show(entity):
    if not os.path.exists(PATH):
        print("No test data yet. Run: python scripts/testdata.py generate --entities ...")
        return 1
    with open(PATH, encoding="utf-8") as fh:
        data = json.load(fh)
    ents = data["entities"]
    for e, rows in ents.items():
        if entity and e != entity:
            continue
        print(f"## {e}")
        for r in rows:
            print(f"- {r['code']}: {r['name']} | {r['date']} | {r['amount']}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--entities", nargs="+", required=True)
    g.add_argument("--count", type=int, default=3)
    s = sub.add_parser("show")
    s.add_argument("entity", nargs="?")
    args = ap.parse_args()
    if args.cmd == "generate":
        generate(args.entities, args.count)
        return 0
    return show(args.entity)


if __name__ == "__main__":
    sys.exit(main())
