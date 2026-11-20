# Security

Use disposable source fixtures and segregated test credentials. Default capture
reads a single process and removes UIA edit values and common secret tokens
from evidence. Free-form labels may still contain sensitive data. Review
artifacts before using a remote provider, sharing them, or publishing them.
Only opt in to screenshots for synthetic fixtures.

Source replay requires a concrete PID for mutation, a unique visible control,
fixture consent and an exact action/control allowlist. Each action starts with
a durable journal entry. Keep session artifacts private and set retention
policies for screenshots, logs, databases and backups. Once retention expires,
remove the chosen evidence directory after verifying that it contains only
disposable data. Keep approved snapshots and backups according to your policy.

The generated API defaults to requiring a secret or explicit disposable demo
mode. Use environment-based or mounted secret configuration, least-privilege
database roles and TLS at the reverse proxy. Never check credentials into
source control. Limit scope before invoking a repair agent. Treat agent
proposals like untrusted changes and verify them in a sandbox.

MCP and skill discovery inventories metadata. Installations, credential grants
and extension execution require a separate explicit authorization through the
chosen agent. Keep provider defaults and OS settings under the operator's
control. Run the dependency audits in CI before release.

Report vulnerabilities privately through the repository owner's GitHub
security reporting channel when enabled. Include the affected version,
reproduction against a disposable fixture and the impact. Remove secrets and
customer data from attachments.
