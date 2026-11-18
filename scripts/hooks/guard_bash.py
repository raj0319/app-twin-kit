"""PreToolUse hook for Bash: ask the user before any command that deletes
or wipes data. Everything else passes through untouched."""
import json
import re
import sys

DANGEROUS = re.compile(
    r"(^|[\s;&|(])(rm|rmdir|del|erase|rd|format|truncate|drop)\b"
    r"|Remove-Item|Clear-Content|DROP\s+(TABLE|DATABASE)|TRUNCATE\s+TABLE",
    re.IGNORECASE,
)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if not DANGEROUS.search(command):
        return 0
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": "This command can delete or wipe data. Please confirm.",
        }
    }
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
