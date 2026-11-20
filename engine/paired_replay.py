"""Replay explicitly paired workflows, normalize evidence, and report differences."""

import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from .playwright_runner import loopback_origin, run_scenarios, validate_scenarios
from .run_state import atomic_json
from .windows_actions import execute_plan
from .workflow_pair import browser_scenarios, load_pairs
from .workflow_quality import audit


def normalize(value, *, mode="text"):
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", str(value)).strip()
    if mode == "text":
        return re.sub(r"\s+", " ", text).casefold()
    if mode == "number":
        from decimal import Decimal, InvalidOperation

        try:
            number = Decimal(text.replace(",", ""))
            if not number.is_finite():
                raise ValueError("not a finite number")
            return str(number.normalize())
        except InvalidOperation as exc:
            raise ValueError(f"not a number: {text!r}") from exc
    if mode == "exact":
        return text
    if mode == "datetime":
        stamp = datetime.fromisoformat(text)
        if stamp.tzinfo is None:
            raise ValueError("timezone is required")
        return stamp.astimezone(timezone.utc).isoformat()
    raise ValueError(f"unknown normalization mode: {mode}")


def compare_paired(source, twin, pairs):
    rows = []
    for pair in pairs:
        sid = pair["id"]
        left, right = source.get(sid), twin.get(sid)
        if left is None or right is None:
            rows.append({"id": sid, "status": "missing_source" if left is None else "missing_twin"})
            continue
        if "__error__" in left or "__error__" in right:
            rows.append(
                {
                    "id": sid,
                    "status": "execution_error",
                    "differences": {
                        "source_error": left.get("__error__"),
                        "browser_error": right.get("__error__"),
                    },
                }
            )
            continue
        differences = {}
        for name, obs in pair["observations"].items():
            mode = obs.get("normalize", "text")
            if name not in left or name not in right or left[name] is None or right[name] is None:
                differences[name] = {
                    "source": left.get(name),
                    "twin": right.get(name),
                    "reason": "missing_observation",
                }
                continue
            if "[redacted]" in str(left[name]) or "[redacted]" in str(right[name]):
                differences[name] = {"reason": "missing_observation"}
                continue
            try:
                a, b = normalize(left[name], mode=mode), normalize(right[name], mode=mode)
            except ValueError:
                differences[name] = {
                    "source": left[name],
                    "twin": right[name],
                    "reason": "normalization_error",
                }
                continue
            if a != b:
                differences[name] = {"source": a, "twin": b}
        complete = not any(item.get("reason") == "missing_observation" for item in differences.values())
        rows.append(
            {
                "id": sid,
                "status": ("fail" if differences else "pass") if complete else "incomplete",
                "differences": differences,
            }
        )
    passed = sum(r["status"] == "pass" for r in rows)
    tested = sum(r["status"] in ("pass", "fail") for r in rows)
    return {
        "total": len(rows),
        "tested": tested,
        "passed": passed,
        "coverage": tested / len(rows) if rows else 0,
        "matched_fraction": passed / len(rows) if rows else None,
        "results": rows,
    }


def run_paired(
    mapping_file,
    *,
    title,
    url,
    output_dir,
    pid=None,
    allow_mutation=False,
    sandbox_confirmed=False,
    allowed_targets=(),
    screenshots=False,
):
    pairs = load_pairs(mapping_file)
    from .workflow_approval import require_approved

    require_approved(pairs)
    review = audit(pairs)
    if not review["ready"]:
        raise ValueError(f"incomplete or incompatible workflow mappings: {review['findings']}")
    loopback_origin(url)
    scenarios = browser_scenarios(pairs)
    validate_scenarios(scenarios)
    if screenshots and not sandbox_confirmed:
        raise PermissionError("screenshots require a disposable fixture")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    source = {}
    # Validate every Windows plan before executing any workflow.
    from .windows_actions import validate_plan

    for pair in pairs:
        validate_plan(
            pair["windows"],
            allow_mutation=allow_mutation,
            sandbox_confirmed=sandbox_confirmed,
            allowed_targets=allowed_targets,
        )
    for index, pair in enumerate(pairs):
        result = execute_plan(
            title,
            pair["windows"],
            pid=pid,
            allow_mutation=allow_mutation,
            sandbox_confirmed=sandbox_confirmed,
            allowed_targets=allowed_targets,
            screenshots=screenshots,
            out_path=output_dir / f"windows-{index:03}.json",
            observations={name: item["windows_automation_id"] for name, item in pair["observations"].items()},
        )
        pid = result["pid"]
        source[pair["id"]] = result["values"]
        atomic_json(output_dir / "source-results.json", source)
    scenarios_file = output_dir / "paired-browser-scenarios.json"
    atomic_json(scenarios_file, scenarios)
    twin = run_scenarios(scenarios_file, url, output_dir / "twin-results.json", screenshots=screenshots)
    report = compare_paired(source, twin, pairs)
    atomic_json(output_dir / "paired-report.json", report)
    return report
