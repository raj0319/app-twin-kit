---
description: List open gaps between the original app and the new system
---

Read `docs/verify/gaps.md`. Show only gaps with status `open`, grouped by severity
in this order: blocks work, wrong result, cosmetic. One line per gap: task, step,
and what differs. End with the count per severity.

If `$ARGUMENTS` is `fix`, switch to FIX mode (see the mode command) and start with
the first "blocks work" gap.
