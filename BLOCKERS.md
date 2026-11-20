# Remaining blockers and scope gaps

- **Provider coverage.** Both CLI executables were found in the user desktop
  context. Claude Code returned an error for a synthetic request and its
  authentication was unconfirmed. Codex was signed in. Its configured default
  model was rejected. The installed CLI exposed a supported model catalog and
  a catalog-selected model completed the live fixture repair.
- **Desktop inference.** The stateful demo uses a reviewed probe matrix. Broad
  autonomous hypothesis selection, role discovery, native dialogs, global input
  recording, and automatic vision or OCR navigation are incomplete. Custom
  controls and untested frameworks require additional fixtures and adapters.
- **Provider and extension operations.** Codex model listing is implemented.
  A comparable Claude listing, enforceable currency budgets, and automated
  activation of previously authorized tools remain open.
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
