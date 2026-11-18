---
name: compare-run
description: How to run one task on both the original app and the new system and record the result as a gap record and a pass/fail line. Use in VERIFY and FIX modes.
---

# Compare one task on both systems

## 1. Pick the task
One file from docs/spec/. Read its raw record in docs/raw/tasks/ for the original's
exact inputs and the data diff it produced.

## 2. Original side
Reuse the raw record's data diff if the inputs are the same. Only re-run on the
original if the inputs changed, and then only on a test record.

## 3. New system side
Start the new system the way docs/architecture.md says. Snapshot, run the task with
the same inputs (through the UI with Playwright or pywinauto, or through the API),
snapshot, diff. Save screenshots to docs/verify/shots/<task>/.

## 4. Compare these six things, in this order
1. Data rows added, removed, changed (field by field).
2. Files produced (exports, PDFs, prints to file).
3. Numbers shown on screen: totals, taxes, balances, counts.
4. Messages: confirmations, validation errors, warnings, and when they appear.
5. Flow: the order of screens and steps.
6. Layout of each screen on the way, by control position and size:
   ```bash
   python scripts/layout.py js        # web twin: run this snippet with Playwright page.evaluate, save the string it returns as docs/verify/layout/<screen>.json
   python scripts/ui_tree.py --title "<twin window>" --out docs/verify/layout/<screen>-twin.md   # desktop twin
   python scripts/layout.py compare docs/spec/layout/<screen>.json <dump> --out docs/verify/layout/<screen>.md
   ```
   The report gives a match % and, per control, missing, moved or resized with
   the pixels to fix. Target: 90% or more, nothing missing.

For a screen whose control tree was thin (an app that draws its own controls), read the labels and
column headers App Watcher's OCR found that the tree missed:
`python scripts/layout.py ocr-extra docs/raw/screens/<screen>.md`, and make sure the twin has them.

7. State check of each screen: `python scripts/state_check.py expect docs/raw "<screen>" --out docs/spec/states/<screen>.json`
   then `python scripts/state_check.py check docs/spec/states/<screen>.json <twin dump> --out docs/verify/state/<screen>.md`.
   It scores fields, actions and grid columns present; target 90% or more, nothing the task needs missing.

Colours, fonts and icons are not compared: the twin has its own look on purpose.

## 5. Record
- For every difference, append a gap using docs/templates/gap.md to docs/verify/gaps.md.
- Add or update one line in docs/verify/report.md: `| <task> | PASS/FAIL | <date> | <gap count> |`.

## 6. Severity guide
- blocks work: the user cannot finish the task.
- wrong result: finishes, but a number, record or file is different.
- cosmetic: same result, different wording or placement (a moved or resized control).
- A control missing from a screen is "blocks work" when the task uses it, else "wrong result".
