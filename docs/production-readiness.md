# Local deployment and integration validation

## Reproducible Docker deployment

Requirements: Docker Desktop with the Compose plugin. Copy the example
environment file and replace both placeholders before starting:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
# Set POSTGRES_PASSWORD and SECRET_KEY in the untracked .env file.
Set-Location docker
docker compose --env-file ../.env up --build -d
docker compose --env-file ../.env ps
```

Compose starts PostgreSQL with a named persistent volume, waits for its
healthcheck, runs Alembic migrations once, then starts the API, a separate
alert worker, and the static frontend. The frontend is served at
`http://localhost:8080`, the API at `http://localhost:8000`, and PostgreSQL
only binds to loopback. `docker compose down` preserves the database volume.
Do not use `docker compose down -v` unless you deliberately want to destroy
the local database.

The API and worker receive the database and JWT settings. Only the worker
receives Telegram credentials. Set `TELEGRAM_BOT_TOKEN` and
`TELEGRAM_CHAT_ID` in `.env` to enable real delivery; when unset, the worker
records notification deliveries as disabled. Set `VITE_API_URL` to the URL
reachable by users' browsers when deploying outside local development.
Production deployments must set `FRONTEND_ORIGINS` appropriately instead of
using local origins.

The API healthcheck validates both process readiness and database access.
The worker is a separate process and handles SIGINT/SIGTERM for graceful
shutdown. Pending metric evaluations and notification deliveries are stored
in PostgreSQL and are recovered after restart. Concurrent jobs use row locks
and `SKIP LOCKED`; duplicate incident/outbox events are constrained by unique
indexes. Telegram's `sendMessage` endpoint does not provide an idempotency
key, so a crash after Telegram accepts a message but before the delivery
status commits can still cause a duplicate retry.

## PostgreSQL migration integration test

The migration test requires a **dedicated, empty, disposable PostgreSQL
database** whose name ends with `_integration_test`. It runs a full fresh
install, rolls back the test-created schema, creates the legacy schema and
sample owner/device, then upgrades again and checks that legacy data survives.
It also verifies the active incident index, unique outbox constraint, and
concurrent `SKIP LOCKED` claims. It refuses to run if the target database has
any tables.

```powershell
# Create this database inside the running PostgreSQL service, replacing the
# username with POSTGRES_USER from the local .env file.
Set-Location docker
docker compose --env-file ../.env exec db sh -c 'createdb -U "$POSTGRES_USER" devpulse_integration_test'
Set-Location ..\backend
$env:POSTGRES_INTEGRATION_URL = (& python -c "from app.core.config import settings; print(settings.database_url.set(host='127.0.0.1', database='devpulse_integration_test').render_as_string(hide_password=False))").Trim()
python -m pytest -q tests/test_postgres_migrations.py
```

The URL is supplied in the local process environment; do not paste it into
chat, documentation, or source control. The migration test leaves the
dedicated database at the current Alembic head.

## Real agent and Telegram end-to-end test

Start the deployment above with a Telegram bot and chat configured in the
local `.env`, then set the API URL and the direct PostgreSQL URL for the same
deployment. The E2E test refuses database names that do not end in
`_e2e_test`. Use a separate Compose project and database initialized with
`POSTGRES_DB=devpulse_e2e_test`; the test registers a user/device and sends
real Telegram messages.

```powershell
$env:POSTGRES_DB = "devpulse_e2e_test"
$env:POSTGRES_PORT = "5433"
$env:API_PORT = "8001"
$env:FRONTEND_PORT = "8081"
$env:VITE_API_URL = "http://localhost:8001"
Set-Location docker
docker compose --project-name devpulse-e2e --env-file ../.env up --build -d
Set-Location ..\backend
$env:DEVPULSE_E2E_API_URL = "http://localhost:8001"
$env:POSTGRES_E2E_URL = (& python -c "from app.core.config import settings; print(settings.database_url.set(host='127.0.0.1', port=5433, database='devpulse_e2e_test').render_as_string(hide_password=False))").Trim()
python -m pytest -q tests/test_live_e2e.py
```

The test enrolls a real local agent process (`python -m agent.main --once`),
uses `psutil` measurements, checks the persisted PostgreSQL sample and
dashboard response, verifies an authenticated WebSocket update, triggers an
offline incident using a short controlled threshold, restarts the agent, and
verifies resolution. When Telegram credentials are configured, it waits for
real firing and resolution messages; otherwise it verifies the worker marks
both deliveries disabled. The test requires the API and PostgreSQL URLs, but
does not claim Telegram delivery when credentials are absent.

## Local checks

The portable test suites use an in-memory SQLite database. PostgreSQL
migration and live agent/Telegram checks are opt-in and must be run against
the dedicated real infrastructure described above:

```powershell
$env:TEST_DATABASE_URL = "sqlite://"
Set-Location backend
python -m pytest -q
Set-Location ..\frontend
npm test
npm run build
npm run lint
```

Never commit `.env`, agent credentials, database URLs, Telegram bot tokens,
or chat identifiers.
