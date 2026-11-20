"""Prerequisite and extension inventory. Discovery never executes configuration."""

import importlib.util
import json
import shutil
import sys
from pathlib import Path

from .agents.runner import health
from .mcp_registry import approvals, discover, pinned


def doctor(choice):
    candidates = ("codex", "claude") if choice == "auto" else (choice,)
    return {
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "node": bool(shutil.which("node")),
        "npm": bool(shutil.which("npm")),
        "psql": bool(shutil.which("psql")),
        "docker": bool(shutil.which("docker")),
        "uia_package": importlib.util.find_spec("pywinauto") is not None,
        "playwright_package": importlib.util.find_spec("playwright") is not None,
        "agents": {agent: health(agent) for agent in candidates},
    }


def tools(root):
    home = Path.home()
    locations = [
        root / ".claude/skills",
        root / ".agents/skills",
        home / ".claude/skills",
        home / ".agents/skills",
        home / ".codex/skills",
    ]
    skills = []
    for location in locations:
        try:
            skills.extend(
                {"name": child.parent.name, "source": str(child), "enabled": False}
                for child in sorted(location.glob("*/SKILL.md"))
            )
        except OSError:
            continue
    granted = approvals(root, home)
    servers = discover(
        [
            root / ".mcp.json",
            home / ".claude.json",
            root / ".codex/config.toml",
            home / ".codex/config.toml",
        ]
    )
    declared = {}
    try:
        declared = json.loads((root / ".mcp.json").read_text(encoding="utf-8")).get("mcpServers", {})
    except (OSError, ValueError):
        pass
    for server in servers:
        server["authorized"] = server["name"] not in granted["disabled"] and (
            server["name"] in granted["enabled"] or granted["all_project"]
        )
        if server["name"] in declared:
            server["pinned"] = pinned(declared[server["name"]])
    return {"mcp": servers, "skills": skills}
