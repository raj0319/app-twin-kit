"""Check a predeclared inventory against hashed repeated live reports and release artifacts."""

import hashlib
import json
from pathlib import Path

from .fidelity import score
from .uas import UniversalAppSpec

CHECKS = ("windows", "browser", "postgresql", "security", "installer", "repair")


def check_artifact(root, entry):
    try:
        path = (root / entry["path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file() or path.stat().st_size == 0:
            return None
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != entry["sha256"]:
                return None
    except (KeyError, OSError, TypeError):
        return None
    return path


def passed_check(root, entry):
    artifact = check_artifact(root, entry)
    if not artifact:
        return False
    try:
        result = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(result, dict) and result.get("passed") is True


def gate(spec_path, manifest_path):
    spec = UniversalAppSpec.load(spec_path)
    manifest_path = Path(manifest_path)
    if not manifest_path.is_file():
        return {"ready": False, "reason": "missing release evidence manifest"}
    root = manifest_path.resolve().parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    checks = {name: passed_check(root, manifest.get("checks", {}).get(name, {})) for name in CHECKS}
    reports = [check_artifact(root, item) for item in manifest.get("paired_runs", [])]
    valid = len(reports) >= 2 and all(reports) and len(set(reports)) == len(reports)
    scores = []
    if valid:
        for file in reports:
            report = json.loads(file.read_text(encoding="utf-8"))
            scores.append(score(spec.workflows, report["results"], unknowns=spec.unknowns))
    reproducible = bool(scores and all(s["results"] == scores[0]["results"] for s in scores[1:]))
    ready = (
        all(checks.values()) and reproducible and all(s["gate_passed"] for s in scores) and not spec.unknowns
    )
    return {
        "ready": ready,
        "reproducible": reproducible,
        "checks": checks,
        "unknowns": spec.unknowns,
        "scores": scores,
    }
