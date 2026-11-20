# Deploy the generated app

## Local checkout

Install Node 20.19+ or 22.12+ and Python 3.11+. Inside `frontend`, run
`npm ci --ignore-scripts` and `npm run build`. Inside `backend`, install
`requirements.txt` in an isolated virtual environment. Set `DATABASE_URL` to a
PostgreSQL URL using the `postgresql+psycopg` driver. Set
`TWIN_FRONTEND_DIST` to the absolute frontend dist path, run
`python -m alembic upgrade head`, then run
`python -m uvicorn main:app --host 127.0.0.1`.

Set a high-entropy `TWIN_API_TOKEN` and enter it in API access in the browser.
Use `TWIN_LOCAL_DEMO=1` only with disposable local data. For production, replace
the shared token hook with your organization's identity and authorization policy.

## Containers

Populate `secrets/postgres_password`, `secrets/database_url` and
`secrets/api_token` using your secret store. Use a URL-safe database password
and a URI of the form `postgresql+psycopg://twin:<password>@db:5432/twin`.
Grant read access to the container's runtime UID where required. Use separate
migration and runtime roles in production. Run `docker compose up --build -d`
and check `docker compose ps -a` and `docker compose logs migrate web`.
The web app and API share port 8000 and the same origin.

Keep PostgreSQL internal. Place a TLS-terminating reverse proxy in front of
the web app, with host allowlisting, trusted proxy configuration and
organization-managed certificates. Health is available at `/api/health`.

## Back up and restore

From a POSIX terminal run
`docker compose exec -T db pg_dump -U twin -d twin -Fc > twin.dump`.
Encrypt backups, restrict access and regularly restore into a **separate**
database with `pg_restore --exit-on-error`. Compare record counts and run
critical workflows against the restored service. Capture and verify a
backup before upgrading. Inspect migrations before applying them and keep the
PostgreSQL volume when updating or uninstalling the application containers.
