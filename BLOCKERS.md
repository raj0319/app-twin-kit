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
- **Desktop inference.** Predictable Windows-to-browser control mappings now
  resolve automatically and ambiguous ones are listed for review. The stateful demo uses a reviewed probe matrix. Broad
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
  primitives, shared-token authentication hooks and relational constraints.
  App-specific permissions, mature identity integration, automatic schema
  evolution, and unsupported behaviors require additional implementation.
- **Product release.** The fixture measurement covers a declared subset.
  The UAS lists unknowns and release evidence remains incomplete.
- **GitHub publication.** GitHub rejected the feature branch push because
  the existing OAuth credential lacks the `workflow` scope required by
  the new GitHub Actions files. The implementation is committed locally.
