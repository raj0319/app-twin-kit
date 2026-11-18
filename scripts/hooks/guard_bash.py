"""PreToolUse hook for Bash.

1. Ask the user before any command that deletes or wipes data.
2. Block binary-analysis tools (REA, Ghidra, IDA, Hopper, decompilers) unless
   state/binary-permission.json says the user owns the program or has written
   permission to analyse it (written by scripts/binary_permission.py grant after
   the user answered the /rea question). Everything else passes through untouched.
"""
import json
import os
import re
import sys

DANGEROUS = re.compile(
    r"(^|[\s;&|(])(rm|rmdir|del|erase|rd|format|truncate|drop)\b"
    r"|Remove-Item|Clear-Content|DROP\s+(TABLE|DATABASE)|TRUNCATE\s+TABLE",
    re.IGNORECASE,
)

# anything that takes a program apart: REA itself and the tools it drives, plus the usual decompilers
BINARY_TOOLS = re.compile(
    r"(^|[\s;&|(\"'])(rea|rea-agents|ghidra\w*|analyzeHeadless|ida|ida64|idat|idat64|hopper\w*|kuna|ilspy\w*|dnspy\w*|dotpeek\w*|"
    r"de4dot|dnlib|monodis|ildasm|radare2|r2|rizin|retdec\w*|binaryninja|binja|objdump|x64dbg|x32dbg|ollydbg|dumpbin|strings)(\.exe)?\b",
    re.IGNORECASE,
)
PERMISSION_FILE = os.path.join("state", "binary-permission.json")


def permission():
    try:
        with open(PERMISSION_FILE, encoding="utf-8") as fh:
            p = json.load(fh)
        return p if isinstance(p, dict) else None
    except Exception:
        return None


def decision(kind, reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": kind, "permissionDecisionReason": reason}}))
    return 0


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    command = (payload.get("tool_input") or {}).get("command") or ""
    if BINARY_TOOLS.search(command) and "binary_permission.py" not in command:
        p = permission()
        if not p or p.get("allowed") is not True:
            return decision(
                "deny",
                "Binary analysis is off: state/binary-permission.json does not record that the user owns this program or has written "
                "permission to analyse it. Run /rea, which asks the user that question first; a 'no' keeps this blocked.",
            )
    if DANGEROUS.search(command):
        return decision("ask", "This command can delete or wipe data. Please confirm.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
