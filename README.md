# App Twin Kit

Build a working twin of a desktop app you already use, verified task by task.

## What this is, in plain words

You have a desktop software your team uses every day. You want a new system
that does the same things. This kit tells an AI (Claude Code) how to do that
job from start to finish:

1. **Watch** the real app the way a person would: open every screen, read
   every field and button, see what it saves and prints.
2. **Try things** itself: type real and wrong values into search boxes,
   filters and forms, and learn from what comes back. It never presses
   Save, Send, Pay or Delete.
3. **Write down** everything it found as a clear spec: each task, each
   screen, each rule, each output.
4. **Build** a new system that does the same things. The AI picks the
   technology and database itself.
5. **Check** the new system against the old one, task by task, and fix the
   differences until they match.

The AI never opens the old app's program code. It works from the real
control names, the data the app writes, and what it learns by trying, so
the twin behaves the same. Each screen also keeps the original's layout:
every field, button and grid sits in the same place at the same size, read
from the control positions, with one screenshot per screen as a reference.
Your users find everything where they expect it. The twin uses its own
colours, fonts and icons and never copies the old app's logos or branding.
A layout check scores every screen and lists anything out of place.

## What you need

- A Windows PC where the old app is installed and logged in.
- [Claude Code](https://claude.com/claude-code) desktop app installed on that PC.
- A person who can show the daily tasks once, or answer a few questions.

## How to start

1. Copy this folder to the PC where the old app runs.
2. Open the folder in Claude Code.
3. Type: `start`

The AI asks four short questions (which app, where it is, what it is used
for, any screen it must not touch) and then runs on its own until the twin
is done. No approvals, no more questions. Every few minutes it prints one
line like:

```
DISCOVER: 40% done | 12 of 30 screens | about 25 min left
```

It works in modes so it does not waste effort or tokens:

| Mode | What it does |
|---|---|
| DISCOVER | Explores the old app and records everything it finds |
| SPEC | Turns the findings into a written spec you can read |
| BUILD | Builds the new system |
| VERIFY | Runs the same tasks on both apps and lists the gaps |
| FIX | Closes the gaps, then goes back to VERIFY |

Commands you can type at any time:

| Command | What it does |
|---|---|
| `/start` | Start, or pick up where it left off |
| `/stop` | Stop now and save the place (Esc also stops) |
| `/progress` | Percent done and approximate time left |
| `/status` | One screen: mode, counts, open gaps |
| `/summary` | Today's one-page summary as a shareable link |
| `/mode verify` | Switch mode (discover, spec, build, verify, fix) |
| `/gaps` | List open differences; `/gaps fix` starts fixing them |

Optional extras:

- **Status line.** Run `claude --plugin-dir mods/twin-status` to keep the
  mode and counts in the status bar (needs Claude Code 2.1.300 or newer).
- **See-and-click fallback.** `.mcp.json` lists Windows-MCP and Playwright.
  Claude Code asks once before starting them. They need `uv` and Node.
- **Show instead of explain.** If a user would rather demonstrate a task,
  the AI can record it with OpenAdapt.

At the end of verification it produces a one-page report you can share with
your team.

## What you get at the end

- `docs/spec/` – a readable description of every task and screen.
- `app/` – the new system, with setup instructions and test data loaded.
- `docs/verify/report.html` – each task passing on both apps.
- `docs/verify/uat-checklist.html` – a tick list for one of your users to
  try the twin with their own hands.
- `docs/summary/` – one page per day: what was learned, built, and what is
  still open. Shared as a link you can forward.

All test data the AI creates starts with `ZZTEST`, so it is easy to spot
and delete afterwards. It never writes to the old app's database directly.

## REA (reverse engineer anything), only for programs you own

The kit has an optional `/rea` step built on [REA](https://github.com/morluto/rea), the open-source
tool that lets Claude Code drive Ghidra, IDA or Hopper and read a program file. It is for programs
you own (your own old software), open-source parts, or a program whose maker gave written permission.
A licensed product bought from a vendor is normally not one, and for those the kit stays outside-only.

How it works: `/rea` asks one question ("own code, written permission, open source, or no?") and writes
the answer to `state/binary-permission.json`; every binary tool stays blocked by the kit's own guard until
that file says yes. When allowed, a subagent uses REA to pull facts (table names, SQL, message texts,
form resources, rules, backends) into `docs/raw/binary/`, and the spec uses them as evidence marked
`binary`. Decompiled code is never stored or copied into the new system; the twin is written from the spec.

Setup, once, by you: install Node.js 22 or newer and run `npx rea-agents setup` in a terminal (it adds
REA's MCP server to Claude Code with your approval), then restart Claude Code.

## Honest limits

- The twin does the same things. It is not a byte-for-byte copy.
- It will never press Send, Pay, Print or Delete in the old app. Those
  actions are recorded as "not pressed" and built from the spec.
- A hidden rule it could not learn by trying is marked UNCONFIRMED in the
  spec and checked in the VERIFY step instead of stopping the run.
- Time estimates are rough. They get better after the first few screens.
- The old app must be open on a real Windows desktop. It cannot be driven
  over plain SSH.

## License

MIT. Use it, change it, share it.
