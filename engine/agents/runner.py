"""Read-only proposal generation through the locally installed provider CLI."""

import json
import os
import re
import shutil
import subprocess
from queue import Empty, Queue
from threading import Thread
from time import monotonic


def command_for(agent, prompt=None, *, model=None):
    if model and not re.fullmatch(r"[A-Za-z0-9_./:-]+", model):
        raise ValueError("invalid provider model identifier")
    if agent == "codex":
        command = ["codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check", "--ephemeral"]
        if model:
            command.extend(["--model", model])
        return [*command, "--", prompt if prompt is not None else "-"]
    if agent == "claude":
        command = ["claude", "-p", "--permission-mode", "default", "--tools", ""]
        if model:
            command.extend(["--model", model])
        return [*command, "--", prompt] if prompt is not None else command
    raise ValueError(f"Unsupported agent: {agent}")


def health(agent):
    executable = shutil.which(agent) if agent in {"codex", "claude"} else None
    if not executable:
        return {"available": False}
    try:
        result = subprocess.run(
            [executable, "--version"], capture_output=True, text=True, timeout=15, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False}
    return {"available": result.returncode == 0, "version": result.stdout.strip()[:100]}


def available(agent):
    return health(agent)["available"]


def models(agent, timeout=10):
    """Query the installed Codex app-server catalog without starting an agent task."""
    executable = shutil.which(agent) if agent == "codex" else None
    if not executable:
        return []
    deadline = monotonic() + timeout
    lines = Queue()
    with subprocess.Popen(
        [executable, "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
    ) as process:

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


def run(agent, prompt, cwd, timeout=900):
    executable = shutil.which(agent)
    if not executable:
        raise RuntimeError(f"{agent} CLI is not available")
    model = os.environ.get(f"TWIN_{agent.upper()}_MODEL")
    deadline = monotonic() + timeout
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("DATABASE_URL", "TWIN_API_TOKEN", "TWIN_FIXTURE", "TWIN_TEST_DATABASE"))
    }

    def invoke(override):
        command = command_for(agent, model=override)
        command[0] = executable
        return subprocess.run(
            command,
            input=prompt,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=max(0.1, deadline - monotonic()),
            check=False,
        )

    try:
        completed = invoke(model)
        if (
            completed.returncode
            and agent == "codex"
            and not model
            and re.search(r"model is not supported|model_not_found", completed.stderr, re.IGNORECASE)
            and deadline - monotonic() > 1
        ):
            catalog = models(agent, timeout=min(10, deadline - monotonic()))
            discovered = next((item["id"] for item in catalog if item["default"]), None)
            if discovered:
                completed = invoke(discovered)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{agent} request timed out") from exc
    if completed.returncode:
        raise RuntimeError(f"{agent} request returned {completed.returncode}; check local sign-in and policy")
    if len(completed.stdout.encode("utf-8")) > 1_000_000:
        raise ValueError("agent response exceeded the proposal size budget")
    return completed.stdout
