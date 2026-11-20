# P0–P2 implementation status

| Item | Status and evidence |
|---|---|
| P0 Windows discovery, recorder and live navigation | WPF tree and exact-control execution verified. WinForms capture verified. Arbitrary app navigation, raw input recording and inaccessible controls remain partial. |
| P0 Behavioral probes | Six controlled live probes across required input, bounds and two-input arithmetic. The fixture matrix is reviewed. General autonomous rule discovery is partial. |
| P0 Versioned UAS | Schema validation, evidence links, version migration, relations, weights and unknowns implemented. |
| P0 React/TypeScript | Deterministic generated app builds and runs in Playwright. Forms, validation, confirmation, navigation and history exercised. |
| P0 FastAPI and PostgreSQL | Migrations, authorization hook, validation, transactions, uniqueness, foreign keys and pagination tested with a local PostgreSQL server. |
| P0 Mapping and differential replay | Exact ID mapping generated for declared cases and paired against browser actions. UI state and persisted values compared. Generic ambiguous mappings still need review. |
| P0 Repair and fidelity | Scoped repair regression and rollback tested. Live seeded fault detected and restored. Authenticated AI-proposed repair is outstanding. Weighted fixture coverage and a separate fail-closed release gate implemented. |
| P1 Agent selection and routing | Auto/default and provider override tested locally. Health, time and call budget implemented. Codex model catalog queried live. Claude-backed execution remains unverified. |
| P1 MCP and skills | Metadata inventory with no command execution. Automated authorized activation is incomplete. |
| P1 Recovery and safety | Atomic checkpoints, run and desktop locks, write-ahead action evidence, exact allowlisting and redaction implemented. Interrupted fixtures require explicit reset. |
| P2 Compatibility | WPF behavior and WinForms discovery measured. Additional framework and owner-drawn coverage remains open. |
| P2 Installer and release | PowerShell per-checkout setup verified in a fresh venv. Clean Windows VM and signed installer evidence pending. |
| P2 Deploy and CI | Docker Compose, migration, authenticated API, health and backup/restore verified. Hosted CI runs pending. |
| P2 Developer and operator docs | User guide, compatibility matrix, deployment instructions and security policy added. |

See [test evidence](TEST_EVIDENCE.md) and [remaining blockers](BLOCKERS.md).
