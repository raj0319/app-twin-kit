"""Capability-based local CLI routing; no guessed model names or credentials."""

import shutil

TASK_ORDER = {
    "discovery": ("claude", "codex"),
    "coding": ("codex", "claude"),
    "verification": ("codex", "claude"),
    "repair": ("codex", "claude"),
}


def select(task="coding", preferred="auto", failures=None, which=None):
    if task not in TASK_ORDER:
        raise ValueError("unknown task")
    which = which or shutil.which
    candidates = (preferred,) if preferred != "auto" else TASK_ORDER[task]
    failures = failures or {}
    usable = [a for a in candidates if a in ("claude", "codex") and which(a)]
    if not usable:
        raise RuntimeError("No usable Claude Code or Codex CLI; install and authenticate one")
    return min(usable, key=lambda a: (failures.get(a, 0), candidates.index(a)))


def route(task, preferred="auto", failures=None, which=None):
    agent = select(task, preferred, failures, which)
    return {
        "agent": agent,
        "model": "cli-configured",
        "task": task,
        "note": "Uses the CLI's authenticated model; no unsupported model switching",
    }
