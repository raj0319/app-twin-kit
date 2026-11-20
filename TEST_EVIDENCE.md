# Test evidence

Measured on November 20, 2026, in a live Windows 10 Pro desktop session,
build 19045. The source fixtures were self-authored PowerShell/WPF and
WinForms apps. The web run used Python 3.12.14, Node 24.11.0, Vite 7.3.8,
Playwright 1.65.2 with Edge 157.0.4341.60, and PostgreSQL 18.0.

| Check | Observed result |
|---|---|
| WPF discovery | Native UIA tree, screenshots, input and button events collected. Six controlled probes witnessed required-field validation, numeric bounds and multiplication. |
| WinForms discovery | UIA found the second fixture's window, edit and lookup button. |
| React and TypeScript | `npm ci --ignore-scripts` and `npm run build` succeeded. The build runs `tsc --noEmit`. |
| Windows and browser | All seven declared workflows matched. Weight 21/21 executed and matched. Behavior 17/17, data 12/12, UI state 6/6. |
| Seeded calculation defect | A one-unit change produced source 33 and twin 34. Only 6/21 weighted points matched and the fixture gate rejected the run. Restoring the calculation returned it to 21/21. |
| Authenticated Codex repair | The account rejected the configured model. The catalog fallback selected a supported model. The one-file proposal was accepted after the live paired regression returned 7/7 workflows and 21/21 weighted points. |
| Standard CLI discovery and resume | `twin start` captured the Windows fixture and routed from a failing Claude request to Codex. A missing evidence field stopped the first draft. After binding provenance to the actual UIA capture, `twin resume` reused the saved draft and generated an app pending live verification. |
| Python and PostgreSQL | 18 tests passed with the disposable integration database, including Alembic upgrade/downgrade, API validation, authorization, foreign keys, pagination and persisted records. |
| Linux portable suite | 16 passed in a Linux container. The PostgreSQL integration test was skipped in this run and exercised on Windows. |
| Deployment and backup | Docker Compose built the Linux image, initialized PostgreSQL, ran Alembic, served health and accepted an authenticated fixture record. A fresh database restored from `pg_dump` contained that record. |
| Installed toolkit | PowerShell setup installed the wheel into a fresh Windows virtual environment. The installed CLI generated a standalone application outside the repository. The release script packaged a committed tree and produced a SHA-256 manifest. |
| Legacy workflow | Existing tracked Claude instructions, skills, hooks, utilities and app tree had no diff. Python compiled the legacy scripts. The layout and UI tree commands displayed help. |
| Lint and dependency scan | Ruff lint and format checks passed. The npm audit and Python dependency audit reported zero known vulnerabilities. |

### Claude adapter session, November 20, 2026 (Claude Code)

Same PC, Python 3.12.10 in a checkout `.venv`, Node 24.11.0, installed Edge,
the checkout's private PostgreSQL 18 cluster on loopback port 55431.

| Check | Observed result |
|---|---|
| Claude adapter failure | Reproduced: `claude -p` printed "Not logged in · Please run /login" (exit 1) with the inherited and with a cleaned environment. `claude auth status` reported `loggedIn: false`. |
| Signed-out routing, live fixture | `twin start --agent claude` captured the WPF window, then stopped with "claude was selected but is not usable ... no fallback to another provider was used" and zero provider calls. `--agent auto` stopped with "No usable Claude Code or Codex CLI". Both checkpoints kept `capture` as completed. |
| Codex reachability | The Codex CLI inside the Codex desktop package cannot be started by other processes (Access is denied); `twin models --agent codex` now reports `unavailable` instead of crashing. |
| Paired replay, repeated | Two fresh runs on a new `prepare` (before and after the mapping change): 7/7 workflows, 21/21 weight, behavior 17/17, data 12/12, UI state 6/6, source and PostgreSQL records equal. |
| Unit tests | 39 passed, 1 skipped (PostgreSQL integration, needs `TWIN_TEST_DATABASE_URL`), including adapter, routing, budget and mapping-resolution tests. Ruff lint and format pass for `engine`, `twin.py`, `tests` and `fixtures`; the legacy `scripts/` folder has 22 pre-existing lint findings. |

Evidence: [docs/evidence/claude-session-2026-11-20](docs/evidence/claude-session-2026-11-20).
Not measured in this session: any successful Claude request, Claude draft,
Claude repair, Codex live calls, the PostgreSQL integration test.

The denominator is the [seven-workflow inventory](docs/evidence/wpf/inventory.json).
UI here measures visible validation and history state. The fixture baseline
does not score visual similarity or behavior outside that inventory. The
product release gate remains closed while requirements and evidence are open.

## Reproduce

Run the commands in the [Windows fixture guide](docs/TOOLKIT.md).
Run `python -m pytest -q` for portable tests. To include PostgreSQL
integration, install the backend requirements and set
`TWIN_TEST_DATABASE_URL` to an empty disposable loopback database named
`app_twin_fixture_ci`.

The committed fixture evidence includes the [baseline](docs/evidence/wpf/baseline.json),
[seeded run](docs/evidence/wpf/seeded.json), [restored run](docs/evidence/wpf/restored.json),
[source and PostgreSQL records](docs/evidence/wpf/persistence.json),
[Codex repair](docs/evidence/wpf/seeded-repair.json),
[paired repair retest](docs/evidence/wpf/repair-retest.json),
[generated source checksums](docs/evidence/wpf/generated-sha256.json),
[native screenshot](docs/evidence/wpf/source-saved.png), and
[browser screenshot](docs/evidence/wpf/browser-saved.png).
