import hashlib
import json

import pytest

from engine.desktop import redact
from engine.fidelity import score
from engine.orchestrator import execute, selected_agent
from engine.release import CHECKS, gate
from engine.repair_loop import repair_file
from engine.run_state import atomic_json, exclusive
from engine.uas import UniversalAppSpec, Workflow
from engine.windows_actions import validate_plan


def test_mutation_permission():
    plan = [{"action": "fill", "automation_id": "code", "value": "ZZTEST"}]
    with pytest.raises(PermissionError):
        validate_plan(plan, allow_mutation=True, sandbox_confirmed=True)
    assert validate_plan(
        plan, allow_mutation=True, sandbox_confirmed=True, allowed_targets={("fill", "code")}
    )
    with pytest.raises(ValueError):
        validate_plan([{"action": "click", "automation_id": "AccessToken"}])
    assert redact("person@example.net") == "[redacted]"


@pytest.mark.parametrize("agent", ["claude", "codex"])
def test_provider_only_and_auto(monkeypatch, agent):
    monkeypatch.setattr("engine.orchestrator.available", lambda candidate: candidate == agent)
    assert selected_agent({"agent": "auto"}) == agent
    assert selected_agent({"agent": agent}) == agent
    with pytest.raises(RuntimeError):
        selected_agent({"agent": "claude" if agent == "codex" else "codex"})


def test_atomic_resume_and_budget(tmp_path, monkeypatch):
    captures = []

    def capture(title, output, **kwargs):
        captures.append(title)
        snapshot = {"pid": 55, "controls": []}
        atomic_json(output, snapshot)
        return snapshot

    monkeypatch.setattr("engine.orchestrator.explore", capture)
    monkeypatch.setattr("engine.orchestrator.available", lambda _: True)
    monkeypatch.setattr("engine.orchestrator.run", lambda *args, **kwargs: "invalid JSON")
    with pytest.raises(RuntimeError, match="budget"):
        execute(tmp_path, title="Fixture", calls=1)
    assert json.loads((tmp_path / "state/twin/run.json").read_text())["status"] == "blocked"
    with pytest.raises(RuntimeError, match="budget"):
        execute(tmp_path, resume=True, calls=1)
    assert captures == ["Fixture"]


def test_process_lock(tmp_path):
    file = tmp_path / "controller.lock"
    with exclusive(file), pytest.raises(RuntimeError, match="Another controller"):
        with exclusive(file):
            pass
    with exclusive(file):
        pass


def test_draft_uses_real_capture_provenance(tmp_path, monkeypatch):
    def capture(title, output, **kwargs):
        snapshot = {"pid": 55, "captured_at": "2026-11-20T12:00:00Z", "controls": []}
        atomic_json(output, snapshot)
        return snapshot

    monkeypatch.setattr("engine.orchestrator.explore", capture)
    monkeypatch.setattr("engine.orchestrator.available", lambda _: True)
    draft = {
        "app_name": "Fixture",
        "entities": [
            {"id": "order", "title": "Orders", "fields": {"code": "text"}, "evidence_ids": ["capture"]}
        ],
        "evidence": [{"id": "capture", "artifact": "untrusted", "observed_at": "forged"}],
        "unknowns": ["Persistence unconfirmed"],
    }
    monkeypatch.setattr(
        "engine.orchestrator.run", lambda *args, **kwargs: "```json\n" + json.dumps(draft) + "\n```"
    )
    assert execute(tmp_path, title="Fixture", calls=1)["status"] == "awaiting_live_verification"
    spec = UniversalAppSpec.load(tmp_path / "state/twin/uas.json")
    assert spec.evidence[0].kind == "uia"
    assert spec.evidence[0].artifact == "capture.json"
    assert spec.evidence[0].observed_at == "2026-11-20T12:00:00Z"


def test_release_rejects_incomplete_and_tampered_report(tmp_path):
    spec = tmp_path / "uas.json"
    inventory = [Workflow("basic", "Basic"), Workflow("critical", "Critical", weight=5)]
    UniversalAppSpec("Fixture", workflows=inventory).save(spec)
    one_pass = [{"id": "basic", "status": "pass"}]
    assert score(inventory, one_pass)["coverage"] == 1 / 6
    manifest = tmp_path / "release.json"
    assert not gate(spec, manifest)["ready"]

    def artifact(name, data):
        path = tmp_path / name
        atomic_json(path, data)
        return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    completed = one_pass + [{"id": "critical", "status": "pass"}]
    checks = {name: artifact(name, {"passed": True}) for name in CHECKS}
    runs = [artifact(f"run{i}.json", {"results": completed}) for i in (1, 2)]
    atomic_json(manifest, {"checks": checks, "paired_runs": runs})
    assert gate(spec, manifest)["ready"]
    failed_check = {**checks, "security": artifact("security-failure.json", {"passed": False})}
    atomic_json(manifest, {"checks": failed_check, "paired_runs": runs})
    assert not gate(spec, manifest)["ready"]
    atomic_json(manifest, {"checks": checks, "paired_runs": runs})
    atomic_json(tmp_path / "run2.json", {"results": one_pass})
    assert not gate(spec, manifest)["ready"]


def test_repair_rolls_back_regression(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    file = app / "code.py"
    file.write_text("value = 1", encoding="utf-8")
    baseline = {"results": [{"id": "a", "status": "fail"}, {"id": "b", "status": "pass"}]}
    other_failure = {"results": [{"id": "a", "status": "pass"}, {"id": "b", "status": "fail"}]}
    kwargs = {"propose": lambda _: '{"content": "value = 2"}', "journal": tmp_path / "repair.json"}
    assert repair_file(app, "code.py", baseline, lambda _: other_failure, **kwargs)["status"] == "unresolved"
    assert file.read_text() == "value = 1"
    perfect = {"results": [{"id": key, "status": "pass"} for key in ("a", "b")]}
    assert (
        repair_file(app, "code.py", baseline, lambda _: perfect, **kwargs)["status"] == "all_workflows_pass"
    )
    assert file.read_text() == "value = 2"
