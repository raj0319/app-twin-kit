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
