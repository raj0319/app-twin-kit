# P0–P2 implementation status

| Item | Status and evidence |
|---|---|
| P0 Windows discovery, recorder and live navigation | WPF tree and exact-control execution verified. WinForms capture verified. Arbitrary app navigation, raw input recording and inaccessible controls remain partial. |
| P0 Behavioral probes | Bounded hypothesis selection (`engine/hypotheses.py`) for required, min/max, allowed values, two-input calculations, branches, persistence and roles, with counterexamples and the next distinguishing probe. Live: selected `code` required and `product(quantity, unit_price)` from six probes, then pinned quantity >= 1 and unit_price >= 0 with four allowlisted probes. Nothing is auto-confirmed. |
| P0 Versioned UAS | Schema validation, evidence links, version migration, relations, weights and unknowns implemented. |
| P0 React/TypeScript | Deterministic generated app builds and runs in Playwright. Forms, validation, confirmation, navigation and history exercised. |
| P0 FastAPI and PostgreSQL | Migrations, authorization hook, validation, transactions, uniqueness, foreign keys and pagination tested with a local PostgreSQL server. `generate --evolve` adds an additive Alembic revision (drops and type changes refused); entity permissions enforce role tokens (401/403). Both verified in PostgreSQL integration tests. |
| P0 Mapping and differential replay | Exact, normalized, prefix-stripped and unique-label mappings resolve automatically with a role guard and a recorded method; ambiguous or unmatched controls are listed with candidates for review. UI state and persisted values compared; live fixture regression 7/7 after the change. |
| P0 Repair and fidelity | Scoped rollback tested. Live seeded fault detected, repaired by authenticated Codex and retested. Weighted fixture coverage and a separate fail-closed release gate implemented. |
| P1 Agent selection and routing | Health checks sign-in through each CLI's status command. An explicit provider never falls back; `auto` skips signed-out CLIs and `run.json` records every attempt, outcome and cost. Claude calls drop a parent Claude Code session's variables, run outside the project, and enforce `--agent-budget-usd`. Codex catalog and repair verified live earlier inside the Codex app. Claude-backed execution remains unverified: the CLI is signed out (see blockers). |
| P1 MCP and skills | Inventory marks servers authorized only from Claude Code's own approvals and flags unpinned packages; `select` returns usable vs needs-approval without enabling or running anything. Activation itself stays with Claude Code. |
| P1 Recovery and safety | Atomic checkpoints, run and desktop locks, write-ahead action evidence, exact allowlisting and redaction implemented. Interrupted fixtures require explicit reset. |
| P2 Compatibility | WPF behavior and WinForms discovery measured. New WinForms fixture: scoped keys (Ctrl+K) and OCR on an owner-drawn control (8/8 live runs, confidence-reported, refuses unknown labels). Menu > Save > native dialog fixed: 16/16 in two batches of 8 (menus via a helper process, dialog buttons via WM_COMMAND). OCR clicks raise the window to topmost only for the click and refuse when covered. Win32, Electron and Java remain open. |
| P2 Installer and release | PowerShell per-checkout setup verified in a fresh venv. Clean Windows VM and signed installer evidence pending. |
| P2 Deploy and CI | Docker Compose, migration, authenticated API, health and backup/restore verified. Hosted CI runs pending. |
| P2 Developer and operator docs | User guide, compatibility matrix, deployment instructions and security policy added. |

See [test evidence](TEST_EVIDENCE.md) and [remaining blockers](BLOCKERS.md).
