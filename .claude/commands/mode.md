---
description: Switch the working mode (discover, spec, build, verify, fix)
argument-hint: discover | spec | build | verify | fix
---

Switch to mode `$ARGUMENTS`.

1. Check the name is one of DISCOVER, SPEC, BUILD, VERIFY, FIX. If not, list them and stop.
2. Write one line to `state/progress.md`: the old mode, the new mode, and why.
3. Write `state/mode.json` as `{"mode": "<NAME>"}`.
4. Say in one line which mode is now active and what the first step is, then start it,
   following the rules for that mode in CLAUDE.md section 4.
