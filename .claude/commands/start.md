---
description: Start or resume the App Twin project
---

Follow CLAUDE.md section 2 and section 10.

If `state/project.json` does not exist: ask the four first-run questions one at a
time, write the answers there, set `state/mode.json` to `{"mode": "DISCOVER"}`,
run `pip install -r scripts/requirements.txt`, and begin DISCOVER mode.

If it exists: read `state/progress.md` and `state/mode.json`, tell the user in one
line where things stand, and continue in the current mode.
