---
description: Start or resume the App Twin project
---

Follow CLAUDE.md section 2 and section 10.

If `state/project.json` does not exist: ask the four first-run questions one at a
time, write the answers there, set `state/mode.json` to
`{"mode": "DISCOVER", "since": "<current ISO time>"}`, run
`pip install -r scripts/requirements.txt`, tell the user in one line that you
will now work on your own and that `/progress`, `/stop` and `/start` are theirs,
and begin DISCOVER mode (CLAUDE.md section 4).

If it exists: read `state/progress.md`, `state/mode.json` and the queue, tell the
user in one line where things stand, and continue in the current mode without
asking anything.
