"""Require explicit, recorded approval before a proposed workflow can run."""

import json
from pathlib import Path

from .workflow_pair import load_pairs


def approve(proposals_file, ids, output_file):
    proposals = load_pairs(proposals_file, allow_proposed=True)
    requested = set(ids)
    if not requested or len(requested) != len(ids):
        raise ValueError("provide unique, nonempty mapping IDs")
    known = {p["id"] for p in proposals}
    if not requested <= known:
        raise ValueError("unknown mapping IDs")
    approved = []
    for p in proposals:
        if p["id"] in requested:
            p["status"] = "user_approved_not_behavior_verified"
            approved.append(p)
    out = Path(output_file)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(approved, indent=2), encoding="utf-8")
    return {"approved": len(approved), "file": str(out)}


def require_approved(pairs):
    for p in pairs:
        if p.get("status") != "user_approved_not_behavior_verified":
            raise PermissionError(f"Mapping {p['id']} requires explicit user approval before live replay")
