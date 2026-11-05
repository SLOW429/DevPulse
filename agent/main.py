import argparse
import logging
import os
import signal
import time

from agent.client import DevPulseClient
from agent.collector import collect_metrics

logger = logging.getLogger("devpulse-agent")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DevPulse host monitoring agent")
    parser.add_argument(
        "--url",
        default=os.getenv("DEVPULSE_API_URL"),
        help="DevPulse API base URL (or DEVPULSE_API_URL)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=30,
        help="Seconds between metric samples (minimum 5; default: 30)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Send one heartbeat and metric sample, then exit",
    )
    return parser.parse_args()


def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    args = parse_args()
    agent_key = os.getenv("DEVPULSE_AGENT_KEY")
    if not args.url:
        raise SystemExit("Set --url or DEVPULSE_API_URL")
    if not agent_key:
        raise SystemExit("Set DEVPULSE_AGENT_KEY")
    if args.interval < 5:
        raise SystemExit("--interval must be at least 5 seconds")

    client = DevPulseClient(args.url, agent_key)
    stopped = False

    def stop_agent(_signum: int, _frame: object) -> None:
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGINT, stop_agent)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, stop_agent)

    while not stopped:
        try:
            client.heartbeat()
            result = client.submit_metrics(collect_metrics())
            logger.info("Submitted metric sample %s", result.get("id", ""))
        except RuntimeError:
            logger.exception("Monitoring cycle failed; will retry next interval")
            if args.once:
                raise
        if args.once:
            return
        deadline = time.monotonic() + args.interval
        while not stopped and time.monotonic() < deadline:
            time.sleep(max(0.0, min(1, deadline - time.monotonic())))


if __name__ == "__main__":
    run()
