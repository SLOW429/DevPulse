import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class DevPulseClient:
    def __init__(self, base_url: str, agent_key: str, timeout: float = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.agent_key = agent_key
        self.timeout = timeout

    def heartbeat(self) -> dict[str, object]:
        return self._post("/agent/heartbeat", {})

    def submit_metrics(self, metrics: dict[str, int | float | str]) -> dict[str, object]:
        return self._post("/agent/metrics", metrics)

    def _post(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.agent_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"DevPulse API returned HTTP {exc.code}: {detail}"
            ) from exc
        except URLError as exc:
            raise RuntimeError(f"Unable to reach DevPulse API: {exc.reason}") from exc
        return json.loads(body)
