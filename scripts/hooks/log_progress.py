"""PostToolUse hook: append one line to state/progress.md for every file
written under docs/ or app/. Keeps a running log so a new session can
resume without re-reading everything."""
import json
import os
import sys
from datetime import datetime


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or ""
    if not path:
        return 0
    root = os.getcwd()
    rel = os.path.relpath(path, root) if os.path.isabs(path) else path
    rel = rel.replace("\\", "/")
    if not (rel.startswith("docs/") or rel.startswith("app/")):
        return 0
    os.makedirs("state", exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    tool = payload.get("tool_name", "write")
    with open(os.path.join("state", "progress.md"), "a", encoding="utf-8") as fh:
        fh.write(f"- {stamp} {tool}: {rel}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
