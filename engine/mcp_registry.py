"""Discover declared MCP servers without executing or exposing configuration."""

import json
import tomllib
from pathlib import Path


def discover(paths):
    found = []
    for path in paths:
        p = Path(path)
        try:
            text = p.read_text(encoding="utf-8")
            data = tomllib.loads(text) if p.suffix == ".toml" else json.loads(text)
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        servers = data.get("mcpServers", data.get("mcp_servers", {}))
        if isinstance(servers, dict):
            for name, entry in servers.items():
                if isinstance(entry, dict):
                    found.append(
                        {
                            "name": name,
                            "source": str(p),
                            "configured": True,
                            "enabled": False,
                            "transport": "remote" if "url" in entry else "stdio",
                        }
                    )
    return found


def require_approval(server, approved_names):
    if server["name"] not in approved_names:
        raise PermissionError("MCP activation requires explicit approval")
    return True


def _load(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def approvals(root, home=None):
    """Servers the operator already approved for this project, read from Claude Code's own settings:
    enabledMcpjsonServers / enableAllProjectMcpServers / mcp__<name> permissions in the project settings,
    and the project entry in ~/.claude.json. Disabled lists win. Nothing is executed or changed."""
    root, home = Path(root), Path(home or Path.home())
    enabled, disabled, allow_all = set(), set(), False
    sources = [_load(root / ".claude/settings.json"), _load(root / ".claude/settings.local.json")]
    user = _load(home / ".claude.json").get("projects", {})
    sources.append(user.get(str(root), user.get(str(root).replace("\\", "/"), {})))
    for data in sources:
        enabled |= set(data.get("enabledMcpjsonServers", []))
        disabled |= set(data.get("disabledMcpjsonServers", []))
        allow_all = allow_all or data.get("enableAllProjectMcpServers") is True
        for rule in (
            data.get("permissions", {}).get("allow", []) if isinstance(data.get("permissions"), dict) else []
        ):
            if isinstance(rule, str) and rule.startswith("mcp__"):
                enabled.add(rule[5:].split("__", 1)[0])
    return {"enabled": enabled, "disabled": disabled, "all_project": allow_all}


def pinned(entry):
    """True when a stdio server's package has an exact version (npx pkg@1.2.3, uvx pkg==1.2.3)."""
    if "url" in entry:
        return True
    args = [str(arg) for arg in entry.get("args", []) if not str(arg).startswith("-")]
    package = args[0] if args else ""
    if package.startswith("@"):
        name, _, version = package[1:].partition("@")
    else:
        name, _, version = package.partition("@")
        if "==" in package:
            version = package.split("==", 1)[1]
    return bool(version) and version != "latest" and any(ch.isdigit() for ch in version)


def select(root, wanted, home=None):
    """Which requested MCP servers may be used now. Unapproved ones are reported, never enabled; the
    operator approves them in Claude Code itself."""
    root = Path(root)
    declared = _load(root / ".mcp.json").get("mcpServers", {})
    approved = approvals(root, home)
    result = {"usable": [], "needs_approval": [], "unknown": []}
    for name in wanted:
        entry = declared.get(name)
        if not isinstance(entry, dict):
            result["unknown"].append(name)
            continue
        ok = name not in approved["disabled"] and (name in approved["enabled"] or approved["all_project"])
        row = {"name": name, "pinned": pinned(entry), "transport": "remote" if "url" in entry else "stdio"}
        (result["usable"] if ok else result["needs_approval"]).append(row)
    return result
