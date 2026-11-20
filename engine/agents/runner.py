"""Read-only proposal generation through the locally installed provider CLI."""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from time import monotonic

AGENTS = ("claude", "codex")
# Provider capabilities the toolkit can enforce through the CLI itself.
CAPABILITIES = {
    "claude": {"budget_usd", "sign_in_status"},
    "codex": {"model_catalog", "sign_in_status"},
}
BUDGET_ENV = "TWIN_AGENT_BUDGET_USD"
SECRET_PREFIXES = ("DATABASE_URL", "TWIN_API_TOKEN", "TWIN_FIXTURE", "TWIN_TEST_DATABASE")
# Variables a parent Claude Code session sets for its own process tree. A nested `claude -p` that inherits
# them joins the parent's session plumbing (simple mode forces API-key auth, the base URL points to the
# host's proxy), so they are dropped. User configuration such as CLAUDE_CONFIG_DIR and API keys stays.
HOST_SESSION_KEEP = {"CLAUDE_CONFIG_DIR"}


def parse_proposal(response):
    text = response.strip().lstrip("﻿")
    if fenced := re.fullmatch(r"```(?:json)?\s*\n(.*?)\n```", text, flags=re.DOTALL):
        text = fenced[1]
    result = json.loads(text)
    if not isinstance(result, dict):
        raise ValueError("provider proposal must be a JSON object")
    return result


def executable(agent):
    """The provider CLI from TWIN_<AGENT>_PATH when set (for example the CLI bundled in a desktop app),
    else from PATH."""
    if agent not in AGENTS:
        return None
    override = os.environ.get(f"TWIN_{agent.upper()}_PATH")
    if override:
        path = Path(override)
        stem_ok = path.stem.lower() == agent and path.suffix.lower() in {"", ".exe", ".cmd", ".bat", ".ps1"}
        return str(path) if stem_ok and path.is_file() else None
    return shutil.which(agent)


def budget():
    raw = os.environ.get(BUDGET_ENV)
    if not raw:
        return None
    value = float(raw)
    if not 0 < value <= 100:
        raise ValueError(f"{BUDGET_ENV} must be between 0 and 100 USD")
    return value


def provider_env(agent):
    env = {key: value for key, value in os.environ.items() if not key.startswith(SECRET_PREFIXES)}
    if agent == "claude" and "CLAUDECODE" in env:
        env = {
            key: value
            for key, value in env.items()
            if key in HOST_SESSION_KEEP
            or not (key.startswith("CLAUDE") or key in {"ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN"})
        }
    return env


def command_for(agent, prompt=None, *, model=None, budget_usd=None):
    if model and not re.fullmatch(r"[A-Za-z0-9_./:\[\]-]+", model):
        raise ValueError("invalid provider model identifier")
    if budget_usd is not None and "budget_usd" not in CAPABILITIES.get(agent, set()):
        raise RuntimeError(f"{agent} CLI cannot enforce a currency budget; unset {BUDGET_ENV} or use claude")
    if agent == "codex":
        command = ["codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check", "--ephemeral"]
        if model:
            command.extend(["--model", model])
        return [*command, "--", prompt if prompt is not None else "-"]
    if agent == "claude":
        command = [
            "claude",
            "-p",
            "--output-format",
            "json",
            "--no-session-persistence",
            "--permission-mode",
            "default",
            "--tools",
            "",
        ]
        if model:
            command.extend(["--model", model])
        if budget_usd is not None:
            command.extend(["--max-budget-usd", f"{budget_usd:.2f}"])
        return [*command, "--", prompt] if prompt is not None else command
    raise ValueError(f"Unsupported agent: {agent}")


def _quiet(command, agent, timeout=15):
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=provider_env(agent),
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def sign_in(agent, exe=None):
    """Whether the CLI reports a signed-in account. Only the yes/no and the method are kept."""
    exe = exe or executable(agent)
    if not exe:
        return {"signed_in": False, "method": "missing"}
    if agent == "claude":
        result = _quiet([exe, "auth", "status"], agent)
        try:
            status = json.loads(result.stdout) if result else {}
        except ValueError:
            status = {}
        return {"signed_in": bool(status.get("loggedIn")), "method": str(status.get("authMethod", "unknown"))}
    result = _quiet([exe, "login", "status"], agent)
    return {"signed_in": bool(result and result.returncode == 0), "method": "codex-login-status"}


def health(agent):
    exe = executable(agent)
    if not exe:
        return {"available": False, "reason": "CLI not found on PATH or TWIN_%s_PATH" % agent.upper()}
    result = _quiet([exe, "--version"], agent)
    if not result or result.returncode:
        return {"available": False, "reason": "CLI did not report a version"}
    account = sign_in(agent, exe)
    report = {
        "available": account["signed_in"],
        "version": result.stdout.strip()[:100],
        "signed_in": account["signed_in"],
        "auth_method": account["method"],
        "capabilities": sorted(CAPABILITIES[agent]),
    }
    if not account["signed_in"]:
        report["reason"] = (
            "not signed in; run `claude auth login`"
            if agent == "claude"
            else "not signed in; run `codex login`"
        )
    return report


def available(agent):
    return health(agent)["available"]


def models(agent, timeout=10):
    """Query the installed Codex app-server catalog without starting an agent task.
    The Claude Code CLI has no model-listing command; see model_listing()."""
    exe = executable(agent) if agent == "codex" else None
    if not exe:
        return []
    deadline = monotonic() + timeout
    lines = Queue()
    try:
        process = subprocess.Popen(
            [exe, "app-server", "--listen", "stdio://"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        # e.g. the CLI bundled inside a packaged desktop app cannot be started by other processes
        return []
    with process:

        def enqueue():
            for line in process.stdout:
                lines.put(line)
            lines.put(None)

        reader = Thread(target=enqueue, daemon=True)
        reader.start()

        def send(message):
            process.stdin.write(json.dumps({"jsonrpc": "2.0", **message}) + "\n")
            process.stdin.flush()

        def response(message_id):
            while monotonic() < deadline:
                line = lines.get(timeout=max(0.001, deadline - monotonic()))
                if line is None:
                    return {}
                item = json.loads(line)
                if item.get("id") == message_id:
                    return item.get("result") or {}
            return {}

        try:
            send(
                {
                    "id": 1,
                    "method": "initialize",
                    "params": {"clientInfo": {"name": "app-twin-kit", "version": "0.2.0"}},
                }
            )
            if not response(1):
                return []
            send({"method": "initialized"})
            send({"id": 2, "method": "model/list", "params": {"limit": 30}})
            return [
                {"id": item["model"], "default": bool(item.get("isDefault"))}
                for item in response(2).get("data", [])
                if item.get("model") and not item.get("hidden")
            ]
        except (Empty, OSError, ValueError):
            return []
        finally:
            process.terminate()
            process.wait(timeout=5)
            reader.join(timeout=1)


def model_listing(agent):
    if agent == "codex":
        state = health("codex")
        listing = {
            "provider": "codex",
            "listing": "catalog",
            "models": models("codex") if state.get("version") else [],
        }
        if not state.get("version"):
            listing.update(listing="unavailable", note=state.get("reason", "Codex CLI could not be started"))
        return listing
    return {
        "provider": "claude",
        "listing": "unavailable",
        "models": [],
        "note": "Claude Code has no model-listing command. It uses its configured model; set "
        "TWIN_CLAUDE_MODEL to an alias such as sonnet or opus, or a full model name your account allows.",
    }


def _reason(completed):
    """One short, credential-free line from a failed provider call."""
    text = (completed.stdout or "") + "\n" + (completed.stderr or "")
    try:
        parsed = json.loads(completed.stdout)
        text = (
            str(parsed.get("result") or parsed.get("subtype") or text) if isinstance(parsed, dict) else text
        )
    except ValueError:
        pass
    line = next((item.strip() for item in text.splitlines() if item.strip()), "no output")
    line = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", "[email]", line)
    line = re.sub(r"(sk-|eyJ)[A-Za-z0-9_\-.]+|[A-Za-z0-9_\-]{32,}", "[redacted]", line)
    return line[:160]


def run(agent, prompt, cwd, timeout=900, usage=None):
    exe = executable(agent)
    if not exe:
        raise RuntimeError(f"{agent} CLI is not available")
    model = os.environ.get(f"TWIN_{agent.upper()}_MODEL")
    limit = budget()
    deadline = monotonic() + timeout
    env = provider_env(agent)

    def invoke(override, workdir):
        command = command_for(agent, model=override, budget_usd=limit)
        command[0] = exe
        return subprocess.run(
            command,
            input=prompt,
            cwd=workdir,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(0.1, deadline - monotonic()),
            check=False,
        )

    try:
        if agent == "claude":
            # An empty folder outside the project, so the CLI does not load the project's CLAUDE.md or hooks.
            with tempfile.TemporaryDirectory(prefix="twin-claude-") as workdir:
                completed = invoke(model, workdir)
        else:
            completed = invoke(model, cwd)
            if (
                completed.returncode
                and not model
                and re.search(r"model is not supported|model_not_found", completed.stderr, re.IGNORECASE)
                and deadline - monotonic() > 1
            ):
                catalog = models(agent, timeout=min(10, deadline - monotonic()))
                discovered = next((item["id"] for item in catalog if item["default"]), None)
                if discovered:
                    completed = invoke(discovered, cwd)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{agent} request timed out") from exc
    output = completed.stdout
    if agent == "claude" and not completed.returncode:
        try:
            envelope = json.loads(output)
        except ValueError as exc:
            raise RuntimeError("claude returned output that is not its JSON result envelope") from exc
        if usage is not None:
            usage.update(
                cost_usd=envelope.get("total_cost_usd"),
                models=sorted((envelope.get("modelUsage") or {}).keys()),
            )
        if envelope.get("is_error") or envelope.get("subtype") not in (None, "success"):
            raise RuntimeError(f"claude request failed: {_reason(completed)}")
        output = envelope.get("result") or ""
    elif completed.returncode:
        raise RuntimeError(f"{agent} request returned {completed.returncode}: {_reason(completed)}")
    if len(output.encode("utf-8")) > 1_000_000:
        raise ValueError("agent response exceeded the proposal size budget")
    return output
