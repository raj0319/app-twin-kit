import json
import tempfile
import unittest
from pathlib import Path

from engine.workflow_approval import approve, require_approved
from engine.workflow_capture import analyze_files, transitions


class TransitionTests(unittest.TestCase):
    def test_changes(self):
        a = {
            "controls": [
                {
                    "automation_id": "A",
                    "control_type": "Text",
                    "name": "Status",
                    "visible": True,
                    "enabled": True,
                }
            ]
        }
        b = {
            "controls": [
                {
                    "automation_id": "A",
                    "control_type": "Text",
                    "name": "Status",
                    "visible": False,
                    "enabled": True,
                }
            ]
        }
        rows = transitions([a, b])
        self.assertEqual(rows[0]["changes"][0]["change"], "state_changed")
        self.assertEqual(rows[0]["status"], "observed_unattributed")

    def test_no_false_rule_claim(self):
        a = {"controls": []}
        rows = transitions([a, a])
        self.assertEqual(rows[0]["changes"], [])

    def test_invalid_snapshot(self):
        with self.assertRaises(ValueError):
            transitions([{}, {"controls": []}])

    def test_analysis_files(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / "a").write_text('{"controls":[]}')
            (p / "b").write_text('{"controls":[]}')
            result = analyze_files([p / "a", p / "b"], p / "out")
            self.assertEqual(result["verified_workflows"], 0)

    def test_approval(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            proposal = {
                "id": "a",
                "windows": [{"action": "read", "automation_id": "A"}],
                "browser": {"path": "/", "steps": []},
                "observations": {"x": {"windows_automation_id": "A", "browser_selector": "#x"}},
                "status": "proposed_unverified",
            }
            (p / "in").write_text(json.dumps([proposal]))
            out = approve(p / "in", ["a"], p / "out")
            self.assertEqual(out["approved"], 1)
            require_approved(json.loads((p / "out").read_text()))
            with self.assertRaises(PermissionError):
                require_approved([proposal])

    def test_unknown_approval_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / "in").write_text("[]")
            with self.assertRaises(ValueError):
                approve(p / "in", ["not-real"], p / "out")
