---
name: binary-insight
description: How to get facts for the spec out of a program file with REA (Reverse Engineer Anything) when, and only when, the user owns the program or may analyse it. Use from /rea or the binary-analyst agent; never for a licensed product without written permission.
license: MIT
compatibility: Needs Node.js 22+, `npx rea-agents setup` done once by the user (registers REA's MCP server), and Hopper, Ghidra, IDA or Kuna for native programs. Works in Claude Code, OpenCode and OpenClaw.
---

# Binary insight with REA

## When this applies

Only when `state/binary-permission.json` says `allowed: true`, which `/rea` writes after the user said the
program is their own code, open source, or that they hold written permission from its maker. For everything
else the kit works from the outside (control tree, data, SQL) and this skill is not used. The Bash guard hook
blocks REA, Ghidra, IDA, Hopper and decompilers until that file exists.

## What REA is

[morluto/rea](https://github.com/morluto/rea), MIT: an MCP server and CLI that lets a coding agent drive
real analysis tools (Hopper, Ghidra, IDA or Kuna for native code; .NET and Java bytecode readers) and answer
questions about a shipped binary. Installed by the user with `npx rea-agents setup` (Node 22+), which adds the
MCP server to Claude Code; `npx rea-agents@latest setup` updates it.

## Steps

1. Record the program: path, size, SHA-256, file version, and the permission record, in `docs/raw/binary/README.md`.
2. Ask REA topic by topic, bounded questions, and write facts only (see the binary-analyst agent for the
   topics and the line format). A fact is a name, a text, a formula, a flow or a backend; never source code.
3. Cross-check with what the kit already observed: `docs/raw/screens/`, `docs/raw/probes/`,
   `docs/raw/data-model.md`. Where the binary contradicts an observation, write both and tag the binary
   line `binary`; VERIFY mode settles it.
4. Hand over: the spec-writer reads `docs/raw/binary/` like any other raw folder. Rules found only in the
   binary are written into the spec as `UNCONFIRMED (binary)` until a probe or a verify run has seen them.

## Never

- Never copy decompiled code into `docs/` or `app/`. The twin is written from the spec, in its own code.
- Never patch, run under a debugger, or modify the program file.
- Never store credentials found in the binary; keep host, port and driver only.
