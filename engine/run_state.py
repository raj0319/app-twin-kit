"""Crash-safe, atomic checkpoints and append-only event audit."""

import json
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".twin-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def checkpoint(path, phase, status, *, evidence=None, error=None):
    if status not in ("pending", "running", "passed", "failed", "blocked"):
        raise ValueError("invalid status")
    path = Path(path)
    current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"phases": {}}
    current["phases"][phase] = {
        "status": status,
        "evidence": evidence or [],
        "error": str(error) if error else None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    atomic_json(path, current)
    return current


def audit(path, event, details=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Caller must not include passwords, tokens, raw keystrokes, or credentials.
    permitted = {
        "phase",
        "status",
        "workflow_id",
        "agent",
        "outcome",
        "evidence_id",
        "id",
        "state",
        "step",
        "action",
        "automation_id",
    }
    clean = {k: v for k, v in (details or {}).items() if k in permitted and isinstance(v, (str, int, bool))}
    with path.open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps({"time": datetime.now(timezone.utc).isoformat(), "event": event, "details": clean})
            + "\n"
        )
        stream.flush()
        os.fsync(stream.fileno())


@contextmanager
def exclusive(path):
    """Hold a process lock. The operating system releases it on interruption."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as lock:
        lock.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError(f"Another controller holds {path.name}") from exc
        yield
