# App Twin Kit

Build a working twin of a desktop app you already use, verified task by task.

## What this is, in plain words

You have a desktop software your team uses every day. You want a new system
that does the same things. This kit tells an AI (Claude Code) how to do that
job from start to finish:

1. **Watch** the real app the way a person would: open every screen, click
   every button, read every field, see what it saves and prints.
2. **Write down** everything it found as a clear spec: each task, each
   screen, each rule, each output.
3. **Build** a new system that does the same things. The AI picks the
   technology and database itself.
4. **Check** the new system against the old one, task by task, and fix the
   differences until they match.

The AI never opens the old app's program code. It only looks at the app
from the outside, like a user with full access. That keeps you on the
right side of the software license.

## What you need

- A Windows PC where the old app is installed and logged in.
- [Claude Code](https://claude.com/claude-code) desktop app installed on that PC.
- A person who can show the daily tasks once, or answer a few questions.

## How to start

1. Copy this folder to the PC where the old app runs.
2. Open the folder in Claude Code.
3. Type: `start`

The AI will ask you a few short questions (which app, where it is, what
it is used for) and then begin on its own. It works in modes so it does
not waste effort or tokens:

| Mode | What it does |
|---|---|
| DISCOVER | Explores the old app and records everything it finds |
| SPEC | Turns the findings into a written spec you can read |
| BUILD | Builds the new system |
| VERIFY | Runs the same tasks on both apps and lists the gaps |
| FIX | Closes the gaps, then goes back to VERIFY |

Before it writes any code it shows you two things for a yes or no: the
technology plan in plain words, and clickable mockups of the main screens.

Commands you can type at any time:

| Command | What it does |
|---|---|
| `/start` | Start, or pick up where it left off |
| `/status` | One screen: mode, counts, open gaps |
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
- `app/` – the new system, with setup instructions.
- `docs/verify/` – a report showing each task passing on both apps.

## Honest limits

- The twin does the same things. It is not a byte-for-byte copy.
- Tasks nobody ever showed the AI will be missed the first time. The
  VERIFY step with a real user catches them.
- If a hidden rule (a formula, a rounding rule) cannot be seen from the
  outside, the AI will tell you and ask instead of guessing silently.

## License

MIT. Use it, change it, share it.
