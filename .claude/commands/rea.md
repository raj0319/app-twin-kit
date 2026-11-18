---
description: Optional binary insight with REA (Reverse Engineer Anything), only for a program the user owns or may analyse
argument-hint: [path to exe or dll]
---

Binary analysis of the original program with REA. This is the one step of the kit that looks inside a
program file, so it runs only for programs the user owns or has written permission to analyse. A licensed
product (an ERP bought from a vendor) is normally NOT such a program; for those the kit stays outside-only.

1. Run `python scripts/binary_permission.py status`.
   - "REFUSED": say in one line that binary analysis stays off for this project and stop.
   - "ALLOWED": go to step 3.
2. Ask the user exactly this, and wait for the answer:
   "Do you own the program `<name from state/project.json or $ARGUMENTS>` (your own code), or do you have
   written permission from its maker to analyse its binary, or is it open source? Answer: own code / written
   permission / open source / no."
   - "no" or anything unclear: run `python scripts/binary_permission.py refuse --program "<name>"`, say in
     one line that REA stays blocked and that the twin is built from the outside only, and stop.
   - one of the three: run `python scripts/binary_permission.py grant --program "<name>" --basis "<answer>" --who "the user"`.
3. Check REA is installed: `npx rea-agents --help` (needs Node.js 22 or newer). If it is not, tell the user
   to run `npx rea-agents setup` once in a terminal (it adds REA's MCP server to Claude Code, with their
   approval, and may install Hopper; an existing Ghidra, IDA or Hopper install is used when present), then
   restart Claude Code and run `/rea` again. Do not run the setup yourself: it changes the user's agent
   configuration.
4. Run the `binary-analyst` subagent on the program (path from `$ARGUMENTS`, else `state/project.json`).
   It writes `docs/raw/binary/*.md` and nothing else. Then say in three lines what it found (tables,
   messages, screens, rules), where the files are, and that SPEC mode will use them as evidence tagged
   `binary`.
5. Rules that always hold, also for the subagent: no decompiled source code is stored under `docs/` or
   copied into `app/`; the twin is written from the spec, in its own code. Findings are facts (names,
   messages, formulas, flows), each with the evidence pointer REA gave.
