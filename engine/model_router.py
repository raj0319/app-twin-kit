"""Capability-based local CLI routing; no guessed model names or credentials."""

import shutil

from .agents.runner import CAPABILITIES

TASK_ORDER = {
    "discovery": ("claude", "codex"),
    "coding": ("codex", "claude"),
    "verification": ("codex", "claude"),
    "repair": ("codex", "claude"),
}


def select(task="coding", preferred="auto", failures=None, which=None, require=()):
    """Pick a provider. An explicit provider is never replaced by another one: if it is unusable or lacks a
    required capability, selection fails. `auto` tries the task's order and skips unusable providers."""
    if task not in TASK_ORDER:
        raise ValueError("unknown task")
    which = which or shutil.which
    require = set(require)
    if preferred != "auto":
        if preferred not in CAPABILITIES:
            raise ValueError(f"unknown provider {preferred}")
        missing = require - CAPABILITIES[preferred]
        if missing:
            raise RuntimeError(
                f"{preferred} cannot enforce {', '.join(sorted(missing))}; no fallback was used"
            )
        if not which(preferred):
            raise RuntimeError(
                f"{preferred} was selected but is not usable (installed and signed in); "
                "no fallback to another provider was used"
            )
        return preferred
    candidates = [a for a in TASK_ORDER[task] if require <= CAPABILITIES[a]]
    failures = failures or {}
    usable = [a for a in candidates if which(a)]
    if not usable:
        need = f" with {', '.join(sorted(require))}" if require else ""
        raise RuntimeError(f"No usable Claude Code or Codex CLI{need}; install and sign in to one")
    return min(usable, key=lambda a: (failures.get(a, 0), candidates.index(a)))


def route(task, preferred="auto", failures=None, which=None, require=()):
    agent = select(task, preferred, failures, which, require)
    return {
        "agent": agent,
        "model": "cli-configured",
        "task": task,
        "note": "Uses the CLI's authenticated model; no unsupported model switching",
    }
