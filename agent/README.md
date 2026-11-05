# DevPulse monitoring agent

The agent runs on the monitored host and reports real system measurements
through the DevPulse API. It requires Python 3.11+ and `psutil`.

See [device monitoring setup](../docs/device-monitoring.md) for user/device
provisioning, installation, configuration, security guidance, and API details.

Quick start from the repository root:

```powershell
python -m pip install -r agent/requirements.txt
$env:DEVPULSE_API_URL = "https://your-devpulse-host"
$env:DEVPULSE_AGENT_KEY = "<provisioned-device-key>"
python -m agent.main
```
