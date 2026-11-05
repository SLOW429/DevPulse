# Device monitoring

The backend provisions devices for authenticated users. Device records have a
stable `agent_id`; each registration returns a random `agent_key` once. Only a
SHA-256 digest and an indexed key prefix are stored. Agent credentials are
independent of user login tokens.

## Database setup

From `backend/`, apply the Alembic migrations before starting the API:

```powershell
alembic upgrade head
uvicorn app.main:app --reload
```

The migration adds stable agent identities and a credential revocation
timestamp to existing device records.

## Provision and manage a device

Register or log in using the existing `/auth/register` and `/auth/login`
endpoints. Use the resulting user bearer token to manage devices:

```text
POST   /devices
GET    /devices
GET    /devices/{device_id}
GET    /devices/{device_id}/metrics?limit=100
POST   /devices/{device_id}/credentials   # rotate and return a new key once
DELETE /devices/{device_id}/credentials   # revoke the current key
```

Metric history is returned newest-first; `limit` is between 1 and 500
(default 100).

The create request accepts `name` and optional `hostname` and `os`. The
response includes device metadata and an `agent_key`; store that key in a
secret manager or environment variable. It is not returned by list/detail
endpoints. Management is scoped to the authenticated user; another user's
device returns 404. Revocation takes effect immediately, and rotation
invalidates the previous key.
After revocation the device remains offline. Rotation clears the prior
last-seen value and the device returns to `unknown` until the newly configured
agent checks in.

## Install and run the monitoring agent

From the repository root, install the standalone agent dependency and set its
configuration in the agent host's environment (Python 3.11+):

```powershell
python -m pip install -r agent/requirements.txt
$env:DEVPULSE_API_URL = "https://your-devpulse-host"
$env:DEVPULSE_AGENT_KEY = "<key returned during device registration>"
python -m agent.main
```

The agent collects CPU utilization, virtual-memory utilization, root-volume
disk utilization, cumulative network bytes sent/received, and host uptime via
`psutil`. It sends an authenticated heartbeat and one metric sample every 30
seconds. `--interval N` changes the interval (minimum 5 seconds), and `--once`
sends one cycle for a connectivity check. Use TLS outside trusted local
development networks. Never place the agent key in command-line arguments,
source control, or logs.

## Ingestion behavior

Agents use the following bearer-authenticated endpoints:

```text
POST /agent/heartbeat
POST /agent/metrics
```

Metric payloads contain `collected_at` (ISO 8601 with timezone), CPU/RAM/disk
percentages from 0 to 100, non-negative cumulative network byte counters, and
non-negative uptime seconds. Naive timestamps, non-finite/out-of-range
percentages, negative counters, and timestamps more than five minutes in the
future are rejected with HTTP 422. Accepted timestamps are normalized to UTC.
`received_at` is set by the database. A successful heartbeat or metric sample
updates the device's last-seen time and marks it online.

Device status becomes offline after 90 seconds without a heartbeat or metric.
The timeout is configurable with `DEVICE_OFFLINE_AFTER_SECONDS`; status is
refreshed and persisted when device management endpoints are read. Devices
that have never reported remain `unknown`.

## Testing

Backend tests can use an isolated in-memory SQLite database without starting
PostgreSQL:

```powershell
Set-Location backend
$env:TEST_DATABASE_URL = "sqlite://"
python -m pytest -q
```

The default test configuration continues to use the isolated
`<POSTGRES_DB>_test` PostgreSQL database.
