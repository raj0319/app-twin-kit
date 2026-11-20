# App Twin Kit CLI

Run on the Windows PC that hosts the source app. Start with a disposable fixture
and local PostgreSQL. The kit supports original app designs and UI you have
permission to reproduce. The generator uses its own visual design.

## Install and inspect

```powershell
.\setup-windows.ps1
.\setup-windows.ps1 -Install -Browser
.\.venv\Scripts\Activate.ps1
twin doctor
twin list-windows
twin capture --title "Exact app title" --pid 12345
```

Pass `-Python C:\Path\To\python.exe` if the Python launcher selects an older
interpreter. The installer builds a checkout-local virtual environment and leaves
browser download to the explicit `-Browser` switch. If scripts are restricted, use
your organization's approved signing and execution policy. To uninstall, remove
only the checkout's `.venv` after closing running tools. Preserve evidence and
generated apps you need. Update by checking out a reviewed release and rebuilding
the virtual environment. Back up the generated app database before migration.

## Capture and generate

`twin start --title "Exact app title" --pid 12345` captures read-only UIA state,
asks an installed agent for a draft UAS, validates it and generates the web app.
`--agent auto` is the default. `--agent codex` and `--agent claude` select one
provider. Sign in through your chosen CLI before use. Provider-configured models
are the default. Override a provider-supported model with `TWIN_CODEX_MODEL` or
`TWIN_CLAUDE_MODEL`. `--agent-timeout` and `--max-agent-calls` bound requests and
time. Provider billing applies. Use `twin status` and `twin resume` to continue
a checkpointed run. A draft that lacks enough evidence may require a reviewed
UAS before generation can continue.

`twin models --agent codex` queries the installed Codex model catalog. When
Codex rejects its configured default and no explicit override was supplied,
the CLI may retry once using the catalog default. Claude uses its CLI model
configuration; it has no listing command, so `twin models --agent claude`
reports `unavailable`.

`twin doctor` shows, per provider, whether the CLI is installed and signed in
(through `claude auth status` or `codex login status`; only yes/no and the
method are kept). `auto` skips a signed-out CLI. An explicitly selected
provider is never replaced by another one: the run stops instead. `twin
status` lists every provider attempt with its outcome and, for Claude, its
cost. `--agent-budget-usd 0.50` caps each Claude request through Claude's own
`--max-budget-usd`; Codex cannot enforce a currency limit, so a budgeted run
refuses Codex. Set `TWIN_CLAUDE_PATH` or `TWIN_CODEX_PATH` to use a CLI that is
not on PATH. Sign the Claude CLI in from a normal terminal, not from a
terminal inside the Claude desktop app, then check `twin doctor --agent claude`.

### Claude-only proof

With the CLI signed in, a disposable fixture database in `DATABASE_URL` and
`TWIN_BROWSER_CHANNEL=msedge`:

```powershell
twin doctor --agent claude
twin start --agent claude --agent-budget-usd 1 --agent-timeout 2 --root state/claude-proof --title "ZZTEST App Twin Order Entry" --pid <fixture pid>
twin status --root state/claude-proof
twin resume --agent claude --agent-budget-usd 1 --root state/claude-proof
python -m fixtures.windows.demo prepare state/claude-repair
npm ci --ignore-scripts --prefix state/claude-repair/app/frontend
npm run build --prefix state/claude-repair/app/frontend
$env:TWIN_AGENT_BUDGET_USD = '1'
python -m fixtures.windows.demo seed-repair state/claude-repair --agent claude
```

The two-second timeout makes the first Claude call fail after the capture is
saved; `status` must show the attempt, and `resume` must reuse the capture.
`seed-repair` must report `all_workflows_pass` with `claude` as the agent.

Review `state/twin/uas.json` for evidence links and unknowns. Capture additional
screens or analyze sequential snapshots with `twin analyze-transitions`.
Use `twin trace-windows --report PLAN.json` with the same fixture consent, PID
and per-action allowlist as paired replay to capture a state graph from an
approved source-only probe.
Use `twin import-legacy --title Example` to read the existing Markdown capture
format. For an offline generator example run
`twin generate --spec fixtures/example-uas.json --output state/example`.
Generated projects include deployment and backup instructions in `DEPLOY.md`.

## Pair and verify

Populate workflow steps with a source `action`, exact `automation_id` and any
fixture-safe `value`. Add `observe` steps with selectors and a normalization
mode (`text`, `exact`, `number` or timezone-bearing `datetime`).
`twin propose-mappings` proposes browser IDs when the generator's control IDs
match the source's explicit IDs. Unresolved cases are reported as gaps.
Review semantics against the actual browser controls, then use
`twin approve-mappings --approve-ids ID` and `twin audit-mappings`.
Use `twin paired-replay --title "Exact app title" --pid 12345 --url http://127.0.0.1:8000`
against the local twin. Fixture writes additionally require `--fixture-consent`
and one `--allow ACTION=ID` per permitted source action/control pair. Screenshot
output requires fixture consent because images can contain sensitive text.

The paired command creates a new evidence directory and rejects reused paths.
After an interrupted write, inspect the JSONL journal, reset the disposable source
according to its own procedure, and choose a new evidence directory.
Blind replay after a crash can duplicate effects.

`twin repair --output state/twin/app --repair-file backend/rules.py --report REPORT.json
--verify-command <executable> <args>` limits agent proposals to one generated file.
Run the program in an isolated development environment. The supplied regression
command must run the relevant lint/build/unit/paired checks and refresh the report.
A proposed edit is rolled back if it loses a previously passing workflow, adds
incomplete evidence, or fails to improve the report.

## Windows fixture demonstration

Install toolkit and generated backend dependencies in an isolated venv. Provide
an **empty disposable** loopback PostgreSQL database named `app_twin_fixture`
and a URL for the fixture role. Do not point this at a shared or production server.

```powershell
python -m pip install ".[windows,browser,dev]" -r engine/templates/backend/requirements.txt
python -m playwright install chromium
$env:DATABASE_URL = 'postgresql+psycopg://fixture:password@127.0.0.1:5432/app_twin_fixture'
python -m fixtures.windows.demo prepare state/demo
npm ci --ignore-scripts --prefix state/demo/app/frontend
npm run build --prefix state/demo/app/frontend
python -m fixtures.windows.demo verify state/demo
python -m fixtures.windows.demo verify state/demo
```

Use `TWIN_BROWSER_CHANNEL=msedge` when measuring against installed Edge. Use a
new directory for another `prepare`. Each `verify` creates unique disposable
fixture records and records source UIA, browser evidence and database effects.
The example enforces availability of its expected controls. Running the
compatibility fixture establishes read-only WinForms discovery for its specific
controls. To activate repository CI live verification, provision a dedicated
trusted interactive Windows runner and set the fixture database URL in Actions.

## Troubleshooting

Use `release-windows.ps1 -OutputDirectory <new folder>` to archive a committed
revision and create a SHA-256 manifest. A code-signing certificate supplied by
thumbprint signs the setup script in the extracted review directory. Review
the release gate before distributing the package.

| Symptom | Check |
|---|---|
| UIA finds zero or multiple windows | Confirm exact title and correct PID in the same desktop session. Keep the app visible. |
| UIA tree omits controls | Inspect the compatibility report for truncation or low accessibility coverage. Add an app-specific adapter or review the screen manually. |
| Generated app cannot start | Confirm the PostgreSQL driver URL, run Alembic from the generated backend, and build the frontend before serving it. |
| Playwright fails on localhost | Check the selected browser binary and bind the generated twin to loopback. Check the backend log for the health endpoint. |
| Provider looks available but returns an error | Check CLI sign-in, provider model availability, network policy and command budget. |
| Fidelity gate fails | Inspect uncovered or mismatching inventory IDs and retain the original run artifacts. |
