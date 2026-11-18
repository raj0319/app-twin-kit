---
description: Stop the App Twin work now and save the place so /start resumes it
---

Stop immediately. Do not start any new subagent or step.

1. Append to `state/progress.md`: the time, the current mode, and exactly where you
   were (which screen, task, build item or gap), one line.
2. Run `python scripts/queue.py list` if in DISCOVER mode so the queue is saved.
3. Say in one line: "Stopped at <where>. Type /start to continue." and end your turn.
