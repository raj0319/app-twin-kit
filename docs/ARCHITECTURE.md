# Architecture and coverage

The legacy Claude Code entry points and Python utilities remain available.
The new Python CLI connects UIA evidence, a validated UAS, deterministic source
generation, paired replay and release evaluation.

1. A process-scoped UIA adapter captures bounded trees with stable IDs and
   timestamps. Live fixture replay uses exact automation IDs and element
   patterns. Its write-ahead journal records the action and resulting state.
2. UAS v0.2.0 adds business entities, relationships, typed rules, workflow
   weights, evidence, permissions and unknowns. Loading v0.1.0 migrates missing
   fields to their defaults. An unsupported version raises an error.
3. Generation emits React/TypeScript and a same-origin FastAPI app with typed
   requests, transactional PostgreSQL writes and an explicit Alembic
   revision. The supported domain rules are required, min, max, equals, one-of
   and integer multiplication. Domain inference beyond these conventions
   requires extension and app-specific evidence.
4. A mapping binds ordered source and browser actions and normalized
   observations. The Playwright runner creates fresh browser contexts. The demo
   reads persisted effects independently from the source fixture file and the
   PostgreSQL database.
5. The final release gate takes a fixed UAS inventory, checks hashes for
   supporting files and repeated reports, recalculates scores and requires
   matching runs and resolved unknowns. Artifact hashes establish integrity.

## Fidelity

Coverage is executed workflow weight divided by all predeclared workflow
weight. Fidelity is matching workflow weight divided by that same denominator.
Missing, redacted and unexecuted cases earn zero points. A workflow contributes
its weight to each of its declared dimensions. UI in the demo means the
observed visible validation and record states. Pixel similarity was outside
the fixture inventory. The narrower fixture gate and the product release gate
answer different questions.

## Windows compatibility matrix

| Framework | Approach | Measured evidence |
|---|---|---|
| WPF | UIA tree, Invoke and Value patterns, exact control IDs | Stateful fixture and paired replay |
| WinForms | UIA tree and exposed names | Fixture window, edit and button |
| Win32 | Exposed UIA/MSAA bridge | Pending fixture verification |
| Electron | Chromium accessibility tree when exposed | Pending fixture verification |
| Java | UIA where exposed, Java Access Bridge would require an adapter | Pending |
| Owner-drawn/custom | Window-only screenshot for disposable fixtures, operator inspection | Screenshot capture measured on WPF. Automated OCR and action fallback are pending. |

The active recorder logs toolkit-issued control operations. The passive recorder
samples UIA focus and state. It has no global keyboard capture. Modal navigation,
native file dialogs, shortcuts, roles, and background behavior depend on the
source adapter and the controlled scenarios available.
