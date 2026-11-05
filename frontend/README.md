# DevPulse web dashboard

The React and TypeScript dashboard displays live device status and the latest
real agent measurements from the DevPulse API. It does not generate sample
metrics. Devices with no agent sample show an explicit no-data state.

## Requirements and local setup

Use Node.js 20.19+ (Node.js 22.12+ recommended). Start the backend and apply
its database migrations first; then:

```powershell
Set-Location frontend
npm install
Copy-Item .env.example .env
npm run dev
```

By default, the frontend talks to `http://127.0.0.1:8000`. Set
`VITE_API_URL` in the frontend `.env` to the backend's externally reachable
HTTP base URL when needed. The dev server is available at
`http://localhost:5173`.

The backend's `FRONTEND_ORIGINS` setting must include the dashboard's exact
origin for browser API calls and WebSocket connections. The default allows
`http://localhost:5173` and `http://127.0.0.1:5173`. Configure production
origins explicitly, for example:

```text
FRONTEND_ORIGINS=["https://monitor.example.com"]
```

Run the production build and test suites with:

```powershell
npm run build
npm test
```

## Using the dashboard

Create an account or sign in with the API's existing email/password flow. The
dashboard summarizes registered devices and the latest CPU, memory, disk,
network byte-counter, and uptime samples. Values appear only after a real
monitoring agent reports them. The device table links to a detail page with
stored metric history; time-range controls filter the available API history.
Use **Alerts** to configure CPU, memory, disk, and offline rules, enable or
disable them, and review firing or resolved incidents. The page refreshes
incident history every 15 seconds and displays Telegram delivery state when
notifications are configured.

Use **Add device** to provision a monitored host. The generated agent
credential is displayed once; copy it to a secure environment variable on the
agent host. Install and run the agent as described in
[device monitoring](../docs/device-monitoring.md).

## Authentication and real-time transport

Login uses the backend's OAuth2 form endpoint and registration uses its JSON
endpoint. The access token is kept in tab-scoped `sessionStorage` (not a
persistent browser cookie or local storage) and sent only as an HTTPS
`Authorization: Bearer` header. Sign-out or a rejected/expired token clears
the session.

The browser obtains a short-lived, single-use WebSocket ticket through an
authenticated HTTPS request. Only that ticket (never the user access token)
is sent to `/ws/dashboard`; the backend checks its expiry and the WebSocket
origin. The socket streams an owner-scoped dashboard snapshot every five
seconds. The UI reconnects with bounded exponential backoff and refreshes the
ticket for each connection.

WebSocket tickets are held in process memory, so the real-time feature expects
a single backend worker. Multi-worker deployments should move ticket storage
to a shared store (such as Redis) before increasing the worker count. Use TLS
for API and WebSocket connections outside local development.

## Alerts and Telegram notifications

The backend runs alert evaluation and notification delivery in a background
worker. Metric ingestion only persists the metric; threshold evaluation and
Telegram requests happen separately. See [alerting and notifications](../docs/alerting.md)
for rule behavior, API endpoints, retry settings, and secure Telegram
configuration.
