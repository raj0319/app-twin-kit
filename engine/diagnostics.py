"""Prerequisite and extension inventory. Discovery never executes configuration."""

import importlib.util
import shutil
import sys
from pathlib import Path

from .agents.runner import health
from .mcp_registry import discover


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
    return {
        "mcp": discover(
            [
                root / ".mcp.json",
                home / ".claude.json",
                root / ".codex/config.toml",
                home / ".codex/config.toml",
            ]
        ),
        "skills": skills,
    }
