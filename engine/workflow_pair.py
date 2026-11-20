"""Explicit mapping of Windows UIA steps to browser selectors; no guessed selectors."""

import json
from pathlib import Path

WINDOWS_ACTIONS = {"observe", "read", "focus", "screenshot", "click", "fill", "select"}
WEB_ACTIONS = {"click", "fill", "select", "check", "uncheck", "press"}


def load_pairs(path, *, allow_proposed=False):
    pairs = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("workflow mappings must be a nonempty list")
    ids = set()
    for pair in pairs:
        sid = pair.get("id")
        if not isinstance(sid, str) or not sid or sid in ids:
            raise ValueError("workflow ids must be unique and nonempty")
        ids.add(sid)
        if pair.get("status") == "proposed_unverified" and not allow_proposed:
            raise ValueError("review proposed workflow mappings before execution")
        if not isinstance(pair.get("windows"), list) or not pair["windows"]:
            raise ValueError("windows steps required")
        if not isinstance(pair.get("browser"), dict):
            raise ValueError("browser mapping required")
        for step in pair["windows"]:
            if step.get("action") not in WINDOWS_ACTIONS:
                raise ValueError("unsupported Windows action")
        for step in pair["browser"].get("steps", []):
            if step.get("action") not in WEB_ACTIONS or not step.get("selector"):
                raise ValueError("unsupported browser action or missing selector")
        if not isinstance(pair.get("observations"), dict) or not pair["observations"]:
            raise ValueError("observation mapping required")
        for name, obs in pair["observations"].items():
            if (
                not name
                or not isinstance(obs, dict)
                or not obs.get("windows_automation_id")
                or not obs.get("browser_selector")
            ):
                raise ValueError("each observation needs Windows automation id and browser selector")
    return pairs


def browser_scenarios(pairs):
    return [
        {
            "id": p["id"],
            "path": p["browser"].get("path", "/"),
            "steps": p["browser"].get("steps", []),
            "observe": {key: obs["browser_selector"] for key, obs in p["observations"].items()},
        }
        for p in pairs
    ]
