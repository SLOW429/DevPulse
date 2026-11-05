# Alerting and notifications

DevPulse evaluates persisted agent measurements asynchronously. The metrics
endpoint stores each accepted sample and returns without waiting for rule
evaluation or Telegram delivery. The API process starts a background worker
unless `ALERTS_WORKER_ENABLED=false`.

## Rules and ownership

Rules are private to their creator and can apply to one owned device or all of
the owner's devices. The authenticated API supports:

```text
GET    /alerts/rules
POST   /alerts/rules
PATCH  /alerts/rules/{rule_id}
DELETE /alerts/rules/{rule_id}
GET    /alerts?active_only=true&limit=50&offset=0
GET    /alerts?active_only=false&severity=critical&device_id=1
```

CPU, memory, and disk thresholds are percentages from 0 to 100 and support
`gt`, `gte`, `lt`, or `lte`. Device-offline rules use `threshold` as the
maximum number of seconds without a check-in (1–86400; omitted thresholds use
`DEVICE_OFFLINE_AFTER_SECONDS`). Evaluation intervals are 5–3600 seconds and
consecutive violations are limited to 1–10. Offline rules for devices that
have never checked in wait for their configured grace period.

Every unique ongoing rule/device condition has one incident. Internally,
legacy `open` and `acknowledged` incidents are exposed as `firing`; a rule
without an active incident is in its OK state. Cleared conditions become
`resolved` and preserve the original trigger time, observed value, threshold,
device name, and resolution time. A stale sample cannot clear an active alert
or count toward firing; device-offline evaluation remains responsible for
detecting missing telemetry.

Rule edits are validated against the complete resulting configuration.
Disabling or deleting a rule resolves its active incidents. Deleting rules,
incidents, or reading history is always owner-scoped; requesting another
owner's device or rule returns not found.

## Notifications

Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in the alert worker
environment to enable delivery. Keep both values in a deployment secret manager or an
untracked `.env`; never put real credentials in source control. The bot token
is a secret setting and is never part of API responses or application log
messages. When either value is absent, notification records are marked
`disabled` and alert evaluation continues.

The database-backed notification outbox records fired and resolved events,
delivery status, attempt count, and a sanitized failure category. Failed
requests are retried with exponential backoff, capped at one hour, up to
`ALERT_NOTIFICATION_MAX_ATTEMPTS`. In-progress deliveries older than
`ALERT_NOTIFICATION_SENDING_TIMEOUT_SECONDS` can be reclaimed after worker
restart. Telegram calls have a bounded timeout. A remote service may accept a
message immediately before a worker crash, so delivery is retryable and
best-effort rather than exactly-once.

Worker settings:

| Environment variable | Default | Purpose |
|---|---:|---|
| `ALERTS_WORKER_ENABLED` | `true` | Run asynchronous alert processing |
| `ALERT_WORKER_POLL_SECONDS` | `1` | Delay between queue polls |
| `ALERT_WORKER_BATCH_SIZE` | `50` | Maximum records processed per pass |
| `ALERT_NOTIFICATION_MAX_ATTEMPTS` | `5` | Attempts before marking delivery failed |
| `ALERT_NOTIFICATION_RETRY_BASE_SECONDS` | `5` | Initial retry delay |
| `ALERT_NOTIFICATION_SENDING_TIMEOUT_SECONDS` | `60` | Reclaim stale in-progress delivery |
| `TELEGRAM_API_TIMEOUT_SECONDS` | `5` | Telegram request timeout |

Database migrations must be applied before starting a release containing
alerts:

```powershell
Set-Location backend
alembic upgrade head
uvicorn app.main:app
```

The backend alert tests use SQLite by setting `TEST_DATABASE_URL=sqlite://`
before running `python -m pytest -q`. Production deployments should use
PostgreSQL and HTTPS.
