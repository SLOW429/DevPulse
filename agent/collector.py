import os
import time
from datetime import UTC, datetime

import psutil


def collect_metrics() -> dict[str, int | float | str]:
    """Collect a real system snapshot suitable for the DevPulse ingestion API."""
    network = psutil.net_io_counters()
    return {
        "collected_at": datetime.now(UTC).isoformat(),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "ram_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage(os.path.abspath(os.sep)).percent,
        "net_bytes_sent": network.bytes_sent,
        "net_bytes_recv": network.bytes_recv,
        "uptime_seconds": max(0, int(time.time() - psutil.boot_time())),
    }
