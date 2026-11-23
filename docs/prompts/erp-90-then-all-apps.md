# Prompt: ERP twins to 90%+, then every kind of Windows app

Paste this whole file into Claude Code (or Codex) opened in the `app-twin-kit`
repository. It is one self-contained brief. Work through it in order and keep
going without routine approvals.

---

## 0. Who you are and what you are building

You are continuing the App Twin Kit: a toolkit that watches a Windows desktop
app, learns what it does, builds a web twin (React/TypeScript + FastAPI +
PostgreSQL) with the same behaviour and the same screen layout, and proves the
match with paired tests (Windows UI Automation on the source, Playwright on the
twin, plus database comparison).

Read first, in this order: `CLAUDE.md`, `IMPLEMENTATION_STATUS.md`,
`BLOCKERS.md`, `TEST_EVIDENCE.md`, `docs/TOOLKIT.md`, `docs/ARCHITECTURE.md`,
then `engine/`, `fixtures/windows/` and `tests/`. Keep everything that already
works working: the legacy Claude workflow (agents, skills, hooks,
`scripts/layout.py`), the `twin` CLI, both providers (Claude and Codex) with
automatic selection, and every safety rule below.

Your job has two phases:

- **Phase A:** ERP-type software reaches **90% or more** measured fidelity.
- **Phase B:** the same pipeline works for every other kind of Windows app or
  `.exe` that can reasonably be twinned, with an honest report for the kinds
  that cannot.

---

## 1. How "90%" is measured (do this before any feature work)

A percentage is only meaningful against a fixed list declared **before**
measuring. Never change the list to raise the score.

1. Write `docs/inventory/erp-capabilities.json`: one entry per capability
   below, each with an id, a weight (1–5, by how much an ERP user depends on
   it), the dimensions it covers (`behavior`, `data`, `ui`, `layout`,
   `report`) and the exact workflow steps that prove it.
2. **Coverage** = weight executed / total weight. **Fidelity** = weight that
   matched on both systems / total weight. Missing, skipped, redacted or
   flaky cases score zero.
3. **Stability:** a capability only counts as matched if it matches in
   **3 consecutive full runs**.
4. **Phase A is done** when fidelity ≥ 90% and coverage ≥ 95% on the ERP
   fixture, stable over 3 consecutive full runs. It must also reach ≥ 80% on
   one real ERP test copy if the owner has supplied one (section 6).
5. Store every run under `docs/evidence/<date>/`: source UIA traces, browser
   traces, screenshots, database diffs, report diffs and the scored JSON. Add a
   one-line summary per run to `TEST_EVIDENCE.md`.

### ERP capability list (the denominator)

| # | Capability | Weight |
|---|---|---|
| 1 | Master data: create, edit, list, delete-protect (customers, items, suppliers) | 5 |
| 2 | Lookups and combo boxes bound to other tables | 4 |
| 3 | Field validation: required, min/max, formats, uniqueness, cross-field rules | 5 |
| 4 | Document numbering sequences (per type, per year or branch) | 4 |
| 5 | Header + line documents: order, invoice, purchase, with add/edit/remove lines | 5 |
| 6 | Line maths: qty × price, discounts (line and document), tax rates, rounding rules, totals | 5 |
| 7 | Document status flows: draft → confirmed → posted → cancelled, with forbidden transitions | 5 |
| 8 | Stock effects: quantity on hand, movements per document, negative-stock rule | 4 |
| 9 | Accounting effects: double-entry postings, ledger balances, period locking | 4 |
| 10 | Lists: search, filter, sort, paging, many columns, column widths | 4 |
| 11 | Reports: on-screen reports with totals and grouping | 4 |
| 12 | Print and export: print preview, PDF, Excel/CSV, same fields and totals | 3 |
| 13 | Users, roles and permissions per screen and action | 3 |
| 14 | Audit trail: who changed what and when | 2 |
| 15 | Dates and periods: fiscal year, date formats, period close | 3 |
| 16 | Multi-company or branch selection at login | 2 |
| 17 | Menus, toolbars, tabs, keyboard shortcuts, dialogs, confirmations | 4 |
| 18 | Same screen layout: positions, sizes, order, grouping, grid columns | 4 |
| 19 | Import (CSV/Excel) of master data | 2 |
| 20 | Error messages: same text, same place, same moment | 3 |

---

## 2. Ground truth first: a self-authored Mini ERP fixture

You cannot measure progress without a source app whose behaviour you know
exactly. Build `fixtures/windows/mini-erp/`: a self-authored WinForms app
(PowerShell or C# .NET 8, nothing licensed) with a local SQLite or JSON store
inside its disposable fixture folder. It must exercise **every** capability in
the list: master data, lookups, a sales order and an invoice with lines, tax
and discount, numbering, status flow, stock, double-entry postings, a list
screen with search/filter/sort, one report, print to PDF, CSV export, two
roles, an audit log, a fiscal period lock, a menu bar, a toolbar, tabs,
shortcuts and confirmation dialogs.

Write its expected behaviour in `fixtures/windows/mini-erp/EXPECTED.md`, so
the inventory steps can be checked against the truth, not against the twin.

---

## 3. Phase A work, in priority order (biggest score gain first)

For each item: write the failing paired test first, implement, run the loop
(section 5) until the inventory entries it covers match in 3 consecutive runs,
then commit.

1. **AI builder as the main build path.** The template generator only makes one
   simple form per table, so it can never reach 90% on an ERP. Make the
   Claude/Codex builder (the legacy `builder` agent workflow, driven by
   `twin`) the main path. It writes the app from the UAS and evidence, inside
   the fixed stack, one capability at a time, and must pass that capability's
   paired test before moving on. Keep the template generator for plain master
   data and as a fallback.
2. **Header + line documents** in the UAS, the builder and the paired runner:
   line grids on the source (UIA DataGrid/List reading and editing) and the
   twin, line maths, totals and rounding.
3. **Grids and lists** on the source: read rows and cells, column headers,
   sort, filter, search, paging; compare with the twin's lists.
4. **Lookups, combos, date pickers, tabs, multi-window flows.**
5. **Inference from data effects:** use App Watcher exports and snapshot diffs
   to learn numbering, status transitions, stock movements and postings. Add
   these hypothesis families to `engine/hypotheses.py`, with
   counterexamples and next probes, and keep "nothing auto-confirmed".
6. **Rules beyond the current five operators:** formats, cross-field, date,
   rounding, tax tables, conditional rules, expressed as data the builder
   implements and the tests check.
7. **Same layout:** feed `scripts/layout.py` layout files into the builder so
   every screen copies positions, sizes and order (never logos, icons or
   colours), and score layout with `layout.py compare` (target ≥ 90% per
   screen).
8. **Reports, print and export:** capture source reports through print to PDF
   or export files, extract text and totals, and compare with the twin's
   PDF/CSV.
9. **Roles, users and audit:** real user accounts in the twin (password hashing,
   sessions), the role matrix learned from probes, and an audit table.
10. **Periods and multi-company.**

---

## 4. Phase B: every other kind of app

Start Phase B only after Phase A is done. For each family, add a small
self-authored fixture, a weighted inventory, and run the same loop to ≥ 90% on
that fixture. Then record per family what worked in the compatibility matrix in
`docs/ARCHITECTURE.md`.

| Family | Fixture to build | Main new work |
|---|---|---|
| Classic Win32 (dialog-based, common controls) | Win32 C or PowerShell + `user32` dialog app | MSAA bridge, list views, tree views, edit controls |
| WinForms / WPF variants | Data-bound grids, MDI windows, ribbons | MDI children, ribbon commands |
| Electron / Chromium desktop apps | Small Electron app | Chromium accessibility tree, or CDP when the app enables it |
| Java Swing / JavaFX | Small Swing app | Java Access Bridge adapter (installation needs approval) |
| Custom-drawn UIs | Owner-drawn controls, canvas buttons, custom grids | OCR navigation with confidence, layout from screenshots, never a blind click |
| Utilities and calculators | Converter or calculator | Pure-logic inference and property tests |
| Small document editors | Notes or rich-text app | Document model, save/open file formats, file diffs |
| Server-backed apps | Fixture talking to a local test API | Record network calls (mitmproxy, owner approval), twin the API contract |

**Out of scope, reported honestly instead of faked:** graphics, CAD, video and
audio editors, games, apps whose logic is mainly on a remote server you cannot
observe, and apps that control hardware. For these, produce a report of what
was captured and why a faithful twin is not possible.

---

## 5. The automatic test → fail → fix → retest loop

Run as a loop with checkpoints (`state/twin/run.json`) so it can stop and
resume:

1. Run the full inventory: paired replay on the source and the twin, layout
   compare, report compare, database compare.
2. Score it and write the run's evidence.
3. Pick the failing capability with the highest weight. Find the root cause
   from the evidence (source trace, browser trace, data diff). Never just retry
   until it passes.
4. Fix the toolkit (`engine/`, builder prompts, fixtures) or the generated app,
   and add a unit or paired test for the fix.
5. Run lint, type checks, build, unit tests, the PostgreSQL integration tests
   and the paired runs. Commit only verified changes, one capability per
   commit, on a feature branch.
6. Go back to step 1. Stop when the Phase A or B target holds for 3
   consecutive full runs, or when a blocker needs the owner (section 7).

Budgets per loop iteration: at most 20 provider calls and a dollar limit set
with `--agent-budget-usd`. Each failing capability gets at most 5 fix attempts
before it is recorded in `BLOCKERS.md` with its evidence, and the loop moves on.

**Report after every 3 iterations,** in one short table: capability, weight,
before, after, status.

---

## 6. Real apps from the owner's PC

The owner may name an installed app (for example their ERP) to test on.

1. **Read only first:** list its windows and controls, check how much UI
   Automation exposes, and report a twinability estimate before touching
   anything.
2. **Real business data must never be changed.** Any save, post, delete,
   print-to-printer or send happens only in a test company, demo database or
   disposable copy the owner confirms in chat. Everything else stays
   observe-only, and search/filter probes only.
3. **Declare before testing:** one critical workflow, its expected steps and
   its observations.
4. **Report fidelity for that app and its inventory only.** Never claim the
   fixture score for a real app.

---

## 7. Safety rules (never relax these)

- Source actions need fixture consent plus an exact allowlist per action and
  control. Alt keys and global input are forbidden; use scoped messages,
  helper processes and posted commands.
- Screenshots and OCR are allowed on disposable fixtures or test data only.
  Redact emails, secrets and typed values in evidence.
- Ask the owner before: installing software, adding credentials or new
  permissions, changing account or repository settings, pushing to `main`,
  and any action that could change important data.
- No silent provider fallback when a provider is chosen explicitly.
- Keep the release gate closed while evidence is missing.

---

## 8. Known blockers to check at the start

- **Claude CLI sign-in.** The Claude CLI must show `"signed_in": true` in
  `twin doctor --agent claude`. Until then, use Codex if available, or do
  non-AI work (fixtures, runners, inventory, layout).
- **The PC must stay on, signed in and unlocked.** Desktop testing cannot run
  while it is off. Use a cloud Windows VM only if the owner provides one with
  a licensed copy of the app.
- **A real ERP test copy** is needed for the real-app part of the Phase A
  target.

---

## 9. Final report

When a phase finishes, or the loop stops, report:

- the inventory score table (before → after) with coverage, fidelity and
  stability
- what passed, what is blocked and why, with evidence paths
- reproduction commands and commit hashes
- an honest list of what still does not match
