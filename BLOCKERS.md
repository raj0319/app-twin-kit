# Remaining blockers and scope gaps

- **Claude Code live runs (blocked on sign-in, 2026-11-20).** The adapter
  failure is diagnosed: the standalone `claude` CLI (npm, 2.1.152) reports
  `loggedIn: false`, auth method `none`, and printed "Not logged in" to a
  request the old adapter summarised as a bare return code. It stayed signed
  out with a clean environment and outside the sandbox. The owner reported a
  successful `claude auth login` in a separate window, but that sign-in was
  not visible to this session and the troubleshooting was stopped. Still
  unproven with Claude: a successful synthetic request, a draft UAS from the
  live WPF fixture, checkpoint and resume after a Claude call, the seeded
  repair and its paired retest. To run them: sign in so that
  `twin doctor --agent claude` shows `"signed_in": true`, then follow
  "Claude-only proof" in [docs/TOOLKIT.md](docs/TOOLKIT.md).
- **Codex outside the Codex app.** On this PC the Codex CLI exists only
  inside the packaged Codex desktop app. Windows refuses to start it from
  other processes ("Access is denied"), so Codex-only and auto-with-Codex
  behaviour was checked by unit tests only. The owner declined installing
  the standalone `@openai/codex` CLI. The earlier live Codex repair ran inside
  the Codex app.
- **Provider capabilities that cannot be enforced.** Claude Code has no
  model-listing command (`twin models --agent claude` reports `unavailable`).
  Codex has no currency limit; `--agent-budget-usd` therefore refuses Codex
  and routes `auto` to Claude only.
- **Menus with native dialogs.** On the WinForms fixture, File > Save followed
  by the confirmation dialog passed 3/3, 1/3 and 1/5 in three batches: the
  Yes press closes the dialog but the save sometimes does not complete. The
  observed status exposes each failure; the root cause is not found yet.
  Keys and OCR were reliable in the same runs.
- **Desktop inference.** Predictable Windows-to-browser control mappings now
  resolve automatically and ambiguous ones are listed for review. Bounded
  hypotheses select validation, bounds, calculations, branches, persistence
  and roles from probes. Broad
  autonomous hypothesis selection, role discovery, native dialogs, global input
  recording, and automatic vision or OCR navigation are incomplete. Custom
  controls and untested frameworks require additional fixtures and adapters.
- **Real source app (priority 2).** No real app, authorization or disposable
  test copy has been supplied yet. Needed: the app's name and install path, a
  disposable copy of the app and its data, one critical workflow with its
  expected steps and observations, and any screens or actions it must not
  touch.
- **Extension operations.** Automated activation of previously authorized
  MCP servers and skills remains open.
- **Release operations.** Local Windows setup, Docker deployment and a
  disposable backup and restore passed. Clean-VM validation, Authenticode
  signing and hosted interactive CI still require infrastructure.
- **Generated application scope.** The backend provides confirmed-rule
  primitives, shared-token and role-token authorization, relational
  constraints and additive schema evolution. Mature identity integration
  (SSO, user accounts), destructive or type-changing migrations, and
  unsupported behaviors require additional implementation.
- **Product release.** The fixture measurement covers a declared subset.
  The UAS lists unknowns and release evidence remains incomplete.
- **GitHub publication.** Re-checked 2026-11-20: the `gh` token for raj0319
  has scopes gist, read:org, repo, still no `workflow`, so the feature branch
  (which adds GitHub Actions files) cannot be pushed. The owner can grant it
  with `gh auth refresh -s workflow`. `main` on GitHub is **not** protected
  (branch protection API: 404); enabling protection is a repository setting
  the owner must approve.
- **MCP servers.** Neither project MCP server (windows-mcp, playwright) is
  approved in Claude Code's settings, and both use unpinned packages.
