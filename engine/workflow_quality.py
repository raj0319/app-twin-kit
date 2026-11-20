"""Detect ambiguous, incomplete, and unsafe workflow mappings before execution."""

from collections import Counter


def audit(pairs):
    findings = []
    for pair in pairs:
        pid = pair["id"]
        windows = pair.get("windows", [])
        browser = pair.get("browser", {})
        source_actions = [
            step for step in windows if step.get("action") in {"click", "fill", "select", "focus"}
        ]
        browser_actions = browser.get("steps", [])
        if len(source_actions) != len(browser_actions) or any(
            original["action"] != twin["action"] or original.get("value") != twin.get("value")
            for original, twin in zip(source_actions, browser_actions)
        ):
            findings.append({"id": pid, "severity": "error", "reason": "missing_or_incompatible_action_pair"})
        ids = [o.get("windows_automation_id") for o in pair.get("observations", {}).values()]
        selectors = [o.get("browser_selector") for o in pair.get("observations", {}).values()]
        if any(not i for i in ids) or any(not s for s in selectors):
            findings.append({"id": pid, "severity": "error", "reason": "missing_observation_target"})
        if any(v > 1 for v in Counter(selectors).values()):
            findings.append(
                {"id": pid, "severity": "warning", "reason": "duplicate_browser_observation_selector"}
            )
        if pair.get("status") not in ("user_approved_not_behavior_verified", "verified"):
            findings.append({"id": pid, "severity": "error", "reason": "unapproved_mapping"})
        if not pair.get("evidence_ids"):
            findings.append({"id": pid, "severity": "warning", "reason": "no_source_evidence_ids"})
    return {
        "ready": not any(x["severity"] == "error" for x in findings),
        "pairs": len(pairs),
        "findings": findings,
    }
