---
description: Write today's one-page summary and publish it as a shareable page
---

1. Run `python scripts/daily_summary.py`.
2. If the Artifact tool is available, publish `docs/summary/latest.html` as a
   private artifact. Reuse the same artifact URL every time (it is saved in
   `state/summary-url.txt`; create it on the first publish). If the tool is not
   available, tell the user the file path instead.
3. Reply with two lines: the link or path, and the single most important thing
   from today in plain words.
