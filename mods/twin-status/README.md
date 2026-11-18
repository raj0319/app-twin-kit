# twin-status mod

A small Claude Code mod that keeps one line in the status bar:

```
twin: DISCOVER · 12 screens · 4 tasks · 0 open gaps
```

It refreshes whenever a file under `docs/` or `state/` changes.

## Use it

From the repo folder:

```bash
claude --plugin-dir mods/twin-status
```

Or set `CLAUDE_CODE_PLUGIN_DIRS` to the folder path so every session loads it.

## Check it

```bash
claude plugin validate mods/twin-status
```
