import json

from engine.mcp_registry import approvals, pinned, select


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_only_operator_approved_servers_are_usable(tmp_path):
    root, home = tmp_path / "repo", tmp_path / "home"
    write(
        root / ".mcp.json",
        {
            "mcpServers": {
                "playwright": {"command": "npx", "args": ["-y", "@playwright/mcp@0.0.41"]},
                "windows-mcp": {"command": "uvx", "args": ["windows-mcp", "serve"]},
                "remote": {"url": "https://example.invalid/mcp"},
            }
        },
    )
    assert select(root, ["playwright", "windows-mcp"], home)["usable"] == []
    write(root / ".claude/settings.local.json", {"enabledMcpjsonServers": ["playwright"]})
    write(
        home / ".claude.json",
        {
            "projects": {
                str(root): {
                    "permissions": {"allow": ["mcp__remote__read"]},
                    "disabledMcpjsonServers": ["windows-mcp"],
                }
            }
        },
    )
    result = select(root, ["playwright", "windows-mcp", "remote", "missing"], home)
    assert [row["name"] for row in result["usable"]] == ["playwright", "remote"]
    assert [row["name"] for row in result["needs_approval"]] == ["windows-mcp"]
    assert result["unknown"] == ["missing"]
    assert result["usable"][0]["pinned"] is True
    write(root / ".claude/settings.json", {"enableAllProjectMcpServers": True})
    assert "windows-mcp" in approvals(root, home)["disabled"]
    assert [r["name"] for r in select(root, ["windows-mcp"], home)["needs_approval"]] == ["windows-mcp"]


def test_pinning():
    assert pinned({"command": "npx", "args": ["-y", "@playwright/mcp@0.0.41"]})
    assert not pinned({"command": "npx", "args": ["-y", "@playwright/mcp@latest"]})
    assert not pinned({"command": "uvx", "args": ["windows-mcp", "serve"]})
    assert pinned({"command": "uvx", "args": ["windows-mcp==0.3.1", "serve"]})
    assert pinned({"url": "https://example.invalid/mcp"})
