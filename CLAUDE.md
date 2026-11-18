# App Twin Kit – instructions for Claude Code

You are building a working twin of a desktop application the user already
uses. Read this whole file once, then follow it. Keep your replies short
and in simple words; the user is not a developer.

## 1. The job in one paragraph

Observe the original app from the outside, exactly as a person with full
access would. Write a complete spec of what it does. Design and build a new
system that does the same things. Prove it by running the same tasks on
both systems and comparing results. Repeat until they match. You choose
the technology and database yourself. Never decompile, disassemble or read
the original app's program code.

## 2. First run: ask only these questions

When the user types `start` and `state/project.json` does not exist, ask
these questions one at a time, in plain words, then write the answers to
`state/project.json` and begin. Do not ask anything else unless a step is
truly blocked.

1. What is the name of the app we are copying, and where is it installed?
   (If they do not know the path, find it yourself from the Start menu,
   running processes, or Program Files.)
2. In one or two lines, what does your team use this app for?
3. Is the app open and logged in on this PC right now, and may I click
   around in it freely? Is there any screen or action I must not touch
   (for example "do not press Send Invoice")?
4. Should the new system be a web app, a desktop app, or your choice?
   (Default: your choice. Pick what fits the users best.)

That is all. Everything else you find out by yourself.

## 3. Rules you always follow

- **Outside only.** Use the UI, screenshots, the accessibility tree, the
  app's own help files, exports, reports, printouts, log files, config
  files, its local database if it is readable, and its network traffic.
  Never run a decompiler on the executable. If a hidden rule cannot be
  found from the outside, say so and ask the user; do not guess silently.
- **Do no harm to live data.** Prefer a test record or a sandbox. Before
  any action that cannot be undone (send, post, delete, pay, print to a
  real printer), stop and ask.
- **Write everything down as you go.** Every finding goes into a file
  under `docs/`. Later sessions must never redo discovery; they read the
  files.
- **Short answers to the user.** One line of status when you change mode
  or finish a step. No long explanations unless asked.
- **Own your decisions.** Technology, database, folder layout, libraries:
  decide, write the reason in `docs/decisions.md`, move on.

## 4. Modes (switchable, to save tokens)

Work is split into modes. Only one mode is active. The active mode is
stored in `state/mode.json`. The user can switch with `mode <name>`.
You switch automatically when a mode's exit condition is met.

| Mode | Goal | Default model | Exit when |
|---|---|---|---|
| DISCOVER | Explore the app, record screens, fields, actions, outputs, data changes | Sonnet for driving the app, Haiku for routine screen reads | Every reachable screen and menu item is logged and every daily task is recorded |
| SPEC | Turn raw findings into a readable spec | Opus for structure, Sonnet for filling sections | Spec covers every task with inputs, rules, outputs, side effects |
| BUILD | Design and build the new system | Opus for architecture, Sonnet for code and screens | All spec items implemented and the app runs |
| VERIFY | Run the same tasks on both apps, diff results, publish the report | Sonnet, Haiku for diffing | Gap list produced and report published |
| FIX | Close gaps from the gap list | Sonnet | Gap list empty, then return to VERIFY once more |

BUILD mode has two approval gates before any code is written:

1. **Plan gate.** After the architect writes `docs/decisions.md` and
   `docs/architecture.md`, enter plan mode and present the stack, database
   and module list to the user in plain words. Build nothing until they
   approve. Do not ask them to choose technology; ask only yes or no.
2. **Design gate.** Run the designer agent to draw the main screens as HTML
   mockups in `docs/design/`. Publish `docs/design/index.html` as a private
   artifact if the Artifact tool is available, otherwise tell the user to
   open the file. Wait for a yes. Then start the builder.

VERIFY mode ends by running `python scripts/report_html.py` and publishing
`docs/verify/report.html` as a private artifact (or pointing the user to the
file). Offer, once, to put the spec in Claude Docs so the user can comment on
each screen; if they say yes, do it and read their comments at the next `/start`.

Token rules that apply in every mode:

- Use subagents for anything that reads a lot (screens, logs, database
  dumps). Give them a narrow brief and ask for a short structured answer.
  Only the summary enters your context.
- Use Haiku for routine, repetitive reads and Sonnet for normal work. Use
  Opus only for architecture and spec structure. Set `model` on each
  subagent accordingly.
- Never re-read a file you have already summarised into `docs/`. Read the
  summary.
- Keep `state/progress.md` updated with what is done and what is next, so
  a new session can resume in one read.
- Compact early: when a mode finishes, write its summary to `docs/` and
  tell the user to run `/compact` if the session is long.

## 5. Agents, skills and hooks (already in this repo)

These already exist under `.claude/`. On the first `start`, check they are
present and run `pip install -r scripts/requirements.txt`. Recreate any
that are missing. Each subagent is a Markdown file in `.claude/agents/`
with frontmatter (`name`, `description`, `model`, `tools`).

| Agent | Model | Job |
|---|---|---|
| `explorer` | sonnet | Drives the original app screen by screen, records the UI tree, screenshots and every control. Writes to `docs/raw/screens/`. |
| `recorder` | haiku | Captures one demonstrated task: steps, inputs, outputs, before/after data snapshot. Writes to `docs/raw/tasks/`. |
| `data-sleuth` | sonnet | Finds and reads the app's data: local DB files, config, exports, logs, network calls. Writes `docs/raw/data-model.md`. |
| `spec-writer` | sonnet | Turns raw findings into `docs/spec/` (one file per task, one per screen, one for rules). |
| `architect` | opus | Picks the stack and database, designs the schema and module layout, writes `docs/decisions.md` and `docs/architecture.md`. |
| `designer` | sonnet | Draws the new system's screens as HTML mockups in `docs/design/` from the spec, for approval before coding. |
| `builder` | sonnet | Implements one spec item at a time in `app/`, with tests. |
| `comparator` | sonnet | Runs one task on both systems, diffs data, files and screenshots, appends to `docs/verify/gaps.md`. |

Project skills in `.claude/skills/<name>/SKILL.md`:

- `observe-app`: how to open the app, read its UI Automation tree,
  screenshot a screen, and log it in the standard format.
- `snapshot-diff`: how to snapshot the app's data (database, files)
  before and after an action and diff it.
- `compare-run`: how to run one task on both systems and record the
  result in the standard gap format.

Hooks in `.claude/settings.json` (scripts in `scripts/hooks/`):

- After every file write under `docs/` or `app/`, append one line to
  `state/progress.md`.
- Before any Bash command containing `rm`, `del`, `drop`, or `truncate`,
  ask the user.

Slash commands in `.claude/commands/`: `/start`, `/mode <name>`, `/status`,
`/gaps` (and `/gaps fix`). Prefer these over free text when the user types
the same words.

MCP servers in `.mcp.json`: `windows-mcp` (see and click the original app
when the UI tree is not enough) and `playwright` (drive a web twin). Claude
Code asks the user once before starting them. Both need `uv` and Node
installed; if they fail to start, say so in one line and continue with
pywinauto and screenshots.

Status line mod in `mods/twin-status/`: shows the mode, counts and open
gaps. Loaded with `claude --plugin-dir mods/twin-status`; needs Claude Code
2.1.300 or newer. If the user's version is older, skip it silently.

## 6. Tools you may set up for observing the app

Install only what you need, and record what you installed in
`docs/decisions.md`.

- **Windows UI Automation**: pywinauto (Python) or FlaUI (C#) to read the
  control tree and drive the app. Prefer this over pixel clicking.
- **Windows-MCP** or another Windows computer-use MCP server, so you can
  see and click the app yourself when the UI tree is not enough.
- **OpenAdapt** (`openadapt-capture`) to record a user demonstrating a
  task when they prefer to show rather than explain. Optional; offer it
  only when a user says "let me show you".
- **screenpipe** for a week of passive screen history before DISCOVER, to
  find tasks nobody remembers to demonstrate. Optional and heavy; only when
  the user asks for it, and tell them it records everything on screen.
- **Process Monitor** to see which files, registry keys and database the
  app touches during an action.
- **mitmproxy** if the app talks to a server, to see its API calls.
- **Database readers** for whatever the app uses (SQLite, Access, SQL
  Server Express, Firebird, flat files). Read only. Never write to the
  original app's database.
- **Claude in Chrome** or Playwright for testing the new system when it
  is a web app.

## 7. Folder layout you maintain

```
state/
  project.json      answers to the first questions
  mode.json         active mode
  progress.md       what is done, what is next (one screen long)
docs/
  raw/              everything observed, unedited
    screens/        one file per screen: controls, screenshot, menu path
    tasks/          one file per recorded task
    data-model.md   tables, files, fields found
  spec/             clean spec, one file per task and per screen
  rules.md          validation rules, calculations, status flows
  decisions.md      why each technology and design choice was made
  architecture.md   schema and module layout of the new system
  design/
    tokens.md       colours, fonts, spacing for the new system
    screens/        HTML mockups, one per screen
    index.html      clickable flow through the mockups
  verify/
    gaps.md         open differences between old and new
    report.md       final pass/fail per task
    report.html     generated by scripts/report_html.py, publishable
app/                the new system
mods/twin-status/   status line mod
.mcp.json           windows-mcp and playwright servers
.claude/
  agents/           subagents listed above
  skills/           project skills listed above
  commands/         /start, /mode, /status, /gaps
  settings.json     hooks and permissions
```

## 8. Standard formats

**Screen record** (`docs/raw/screens/<name>.md`): menu path, purpose,
list of controls (type, label, default value, required?), actions
available, screenshot path, what each action changes.

**Task record** (`docs/raw/tasks/<name>.md`): who does it, how often,
numbered steps with the exact control used, inputs entered, outputs seen,
data snapshot diff, files created, printouts.

**Gap record** (`docs/verify/gaps.md`): task name, step number, what the
old app did, what the new app did, severity (blocks work / wrong result /
cosmetic), status.

## 9. Definition of done

- Every menu item and screen of the original is in `docs/raw/screens/`.
- Every daily task is in `docs/spec/` and implemented in `app/`.
- `docs/verify/report.md` shows every task passing on both systems.
- `app/README.md` tells a non-developer how to install and run the new
  system.
- `docs/verify/gaps.md` has no open items of severity "blocks work" or
  "wrong result".

## 10. Resuming

On any later `start`, read `state/progress.md` and `state/mode.json`,
tell the user in one line where things stand, and continue. Never ask the
first-run questions again.
