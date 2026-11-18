"""Screen queue for DISCOVER mode, kept in state/queue.json.

  python scripts/queue.py add "Sales > Invoices" "Sales > Customers"
  python scripts/queue.py start "Sales > Invoices"
  python scripts/queue.py done "Sales > Invoices"
  python scripts/queue.py next          # prints the next pending screen
  python scripts/queue.py list
"""
import json
import os
import sys
from datetime import datetime

PATH = os.path.join("state", "queue.json")


def load():
    if not os.path.exists(PATH):
        return []
    with open(PATH, encoding="utf-8") as fh:
        return json.load(fh)


def save(q):
    os.makedirs("state", exist_ok=True)
    with open(PATH, "w", encoding="utf-8") as fh:
        json.dump(q, fh, indent=1)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd, names = argv[1], argv[2:]
    q = load()
    byname = {e["name"]: e for e in q}
    now = datetime.now().isoformat(timespec="seconds")

    if cmd == "add":
        added = 0
        for n in names:
            if n not in byname:
                q.append({"name": n, "status": "pending", "started": None, "finished": None})
                added += 1
        save(q)
        print(f"added {added}, total {len(q)}")
    elif cmd == "start":
        for n in names:
            e = byname.get(n) or q.append({"name": n, "status": "pending"}) or q[-1]
            e["status"], e["started"] = "running", now
        save(q)
    elif cmd == "done":
        for n in names:
            e = byname.get(n)
            if e:
                e["status"], e["finished"] = "done", now
        save(q)
    elif cmd == "next":
        pend = [e["name"] for e in q if e["status"] == "pending"]
        print(pend[0] if pend else "")
    elif cmd == "list":
        for e in q:
            print(f"[{e['status']:7}] {e['name']}")
        done = sum(1 for e in q if e["status"] == "done")
        print(f"{done}/{len(q)} done")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
