"""Infer candidate validation rules from controlled input/output experiments.
Candidates are never silently promoted to confirmed rules.
"""

import json
from pathlib import Path


def infer(experiments):
    proposals = []
    for case in experiments:
        if not isinstance(case, dict) or not all(
            k in case for k in ("entity", "field", "input", "accepted", "evidence_id")
        ):
            raise ValueError("experiments require entity, field, input, accepted and evidence_id")
        value = case["input"]
        if case["accepted"] is False and (value is None or value == ""):
            proposals.append(
                {
                    "entity": case["entity"],
                    "field": case["field"],
                    "operator": "required",
                    "status": "candidate_unconfirmed",
                    "evidence_ids": [case["evidence_id"]],
                }
            )
        if case["accepted"] is False and isinstance(value, (int, float)) and not isinstance(value, bool):
            proposals.append(
                {
                    "entity": case["entity"],
                    "field": case["field"],
                    "hypothesis": "numeric boundary or cross-field validation",
                    "tested_value": value,
                    "status": "candidate_unconfirmed",
                    "evidence_ids": [case["evidence_id"]],
                }
            )
    return proposals


def save(experiments_path, out_path):
    proposals = infer(json.loads(Path(experiments_path).read_text(encoding="utf-8")))
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(proposals, indent=2), encoding="utf-8")
    return {"candidates": len(proposals), "confirmed": 0, "file": str(p)}
