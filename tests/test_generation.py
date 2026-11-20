import json
from pathlib import Path

import pytest

from engine.generate import generate
from engine.paired_replay import compare_paired, normalize
from engine.uas import UniversalAppSpec
from engine.workflow_quality import audit

EXAMPLE = Path(__file__).resolve().parents[1] / "fixtures/example-uas.json"


def test_generator_is_deterministic_and_rejects_overwrite(tmp_path):
    app = tmp_path / "app"
    result = generate(EXAMPLE, app)
    assert result["confirmed_rules"] == 3
    assert generate(EXAMPLE, app) == result
    source = app / "frontend/src/main.tsx"
    source.write_text("local edits", encoding="utf-8")
    with pytest.raises(FileExistsError):
        generate(EXAMPLE, app)
    assert source.read_text(encoding="utf-8") == "local edits"
    migration = (app / "backend/migrations/versions/0001_initial.py").read_text(encoding="utf-8")
    assert "op.create_foreign_key" in migration and "op.create_table" in migration


def test_load_migrates_legacy_and_rejects_future_version(tmp_path):
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps({"app_name": "Legacy", "schema_version": "0.1.0"}), encoding="utf-8")
    assert UniversalAppSpec.load(path).schema_version == "0.2.0"
    path.write_text(json.dumps({"app_name": "Future", "schema_version": "99"}), encoding="utf-8")
    with pytest.raises(ValueError, match="unsupported UAS"):
        UniversalAppSpec.load(path)


def test_missing_mapping_and_redacted_observations_are_gaps():
    pair = {
        "id": "workflow",
        "status": "user_approved_not_behavior_verified",
        "windows": [{"action": "click", "automation_id": "entry"}],
        "browser": {"steps": []},
        "observations": {"text": {"windows_automation_id": "status", "browser_selector": "#status"}},
    }
    assert not audit([pair])["ready"]
    redacted = {"workflow": {"text": "[redacted]"}}
    assert compare_paired(redacted, redacted, [pair])["coverage"] == 0
    assert normalize("2026-11-20T10:00:00+05:30", mode="datetime") == "2026-11-20T04:30:00+00:00"
