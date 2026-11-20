import json
import subprocess
from pathlib import Path

import pytest

from engine.agents import runner
from engine.model_router import select


def completed(stdout="", stderr="", code=0):
    return subprocess.CompletedProcess([], code, stdout, stderr)


def test_claude_command_is_tool_free_json_and_budgeted():
    command = runner.command_for("claude", model="sonnet", budget_usd=0.5)
    assert command[:2] == ["claude", "-p"]
    assert command[command.index("--output-format") + 1] == "json"
    assert command[command.index("--tools") + 1] == ""
    assert "--no-session-persistence" in command
    assert command[command.index("--max-budget-usd") + 1] == "0.50"
    with pytest.raises(RuntimeError, match="cannot enforce a currency budget"):
        runner.command_for("codex", budget_usd=0.5)
    with pytest.raises(ValueError):
        runner.command_for("claude", model="sonnet; rm")


def test_nested_session_variables_are_dropped(monkeypatch):
    for key, value in {
        "CLAUDECODE": "1",
        "CLAUDE_CODE_SIMPLE": "1",
        "CLAUDE_CODE_SESSION_ID": "host",
        "ANTHROPIC_BASE_URL": "http://host-proxy",
        "CLAUDE_CONFIG_DIR": "C:/cfg",
        "ANTHROPIC_API_KEY": "user-key",
        "DATABASE_URL": "postgresql://secret",
    }.items():
        monkeypatch.setenv(key, value)
    env = runner.provider_env("claude")
    assert not {"CLAUDECODE", "CLAUDE_CODE_SIMPLE", "CLAUDE_CODE_SESSION_ID", "ANTHROPIC_BASE_URL"} & set(env)
    assert env["CLAUDE_CONFIG_DIR"] == "C:/cfg" and env["ANTHROPIC_API_KEY"] == "user-key"
    assert "DATABASE_URL" not in env
    assert runner.provider_env("codex")["CLAUDECODE"] == "1"


def test_explicit_provider_never_falls_back():
    only_codex = lambda agent: agent == "codex"  # noqa: E731
    with pytest.raises(RuntimeError, match="no fallback"):
        select("discovery", "claude", which=only_codex)
    assert select("discovery", "auto", which=only_codex) == "codex"
    assert select("discovery", "auto", which=lambda _: True) == "claude"
    assert select("repair", "auto", which=lambda _: True) == "codex"


def test_budget_limits_routing_to_enforcing_providers():
    everyone = lambda _: True  # noqa: E731
    assert select("repair", "auto", which=everyone, require={"budget_usd"}) == "claude"
    with pytest.raises(RuntimeError, match="cannot enforce"):
        select("repair", "codex", which=everyone, require={"budget_usd"})
    with pytest.raises(RuntimeError, match="budget_usd"):
        select("repair", "auto", which=lambda agent: agent == "codex", require={"budget_usd"})


def test_claude_run_reads_envelope_outside_project(monkeypatch, tmp_path):
    calls = []

    def fake(command, **kwargs):
        calls.append((command, kwargs))
        envelope = {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": '{"ok": true}',
            "total_cost_usd": 0.0123,
            "modelUsage": {"claude-sonnet": {}},
        }
        return completed(json.dumps(envelope))

    monkeypatch.setattr(runner, "executable", lambda agent: "claude.cmd")
    monkeypatch.setattr(runner.subprocess, "run", fake)
    monkeypatch.setenv(runner.BUDGET_ENV, "0.25")
    usage = {}
    assert runner.parse_proposal(runner.run("claude", "prompt", tmp_path, usage=usage)) == {"ok": True}
    command, kwargs = calls[0]
    assert kwargs["input"] == "prompt"
    assert not Path(kwargs["cwd"]).is_relative_to(tmp_path)
    assert command[command.index("--max-budget-usd") + 1] == "0.25"
    assert usage == {"cost_usd": 0.0123, "models": ["claude-sonnet"]}


@pytest.mark.parametrize(
    "result, message",
    [
        (completed("Not logged in · Please run /login\n", code=1), "Not logged in"),
        (
            completed(json.dumps({"subtype": "error_max_budget_usd", "is_error": True, "result": ""})),
            "error_max_budget_usd",
        ),
        (
            completed(
                json.dumps({"subtype": "success", "is_error": True, "result": "API Error: overloaded"})
            ),
            "overloaded",
        ),
    ],
)
def test_claude_failures_are_reported_without_secrets(monkeypatch, tmp_path, result, message):
    monkeypatch.setattr(runner, "executable", lambda agent: "claude.cmd")
    monkeypatch.setattr(runner.subprocess, "run", lambda *a, **k: result)
    with pytest.raises(RuntimeError, match=message):
        runner.run("claude", "prompt", tmp_path)


def test_reason_redacts_accounts_and_tokens():
    line = runner._reason(completed("failed for person@example.net with sk-ant-abc123def456\n", code=1))
    assert "person@example.net" not in line and "abc123" not in line


def test_health_requires_sign_in(monkeypatch):
    monkeypatch.setattr(runner, "executable", lambda agent: f"{agent}.cmd")

    def quiet(command, agent, timeout=15):
        if command[1] == "--version":
            return completed("2.1.152 (Claude Code)")
        if command[1:] == ["auth", "status"]:
            return completed(json.dumps({"loggedIn": False, "authMethod": "none", "email": "x@y.z"}))
        return completed(code=1)

    monkeypatch.setattr(runner, "_quiet", quiet)
    report = runner.health("claude")
    assert report["available"] is False and report["signed_in"] is False
    assert "claude auth login" in report["reason"]
    assert "x@y.z" not in json.dumps(report)
    assert runner.health("codex")["available"] is False


def test_executable_override(monkeypatch, tmp_path):
    exe = tmp_path / "codex.exe"
    exe.write_bytes(b"")
    monkeypatch.setenv("TWIN_CODEX_PATH", str(exe))
    assert runner.executable("codex") == str(exe)
    monkeypatch.setenv("TWIN_CODEX_PATH", str(tmp_path / "other.exe"))
    assert runner.executable("codex") is None


def test_claude_model_listing_is_reported_unavailable():
    listing = runner.model_listing("claude")
    assert listing["listing"] == "unavailable" and listing["models"] == []
