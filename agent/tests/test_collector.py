from agent.collector import collect_metrics


def test_collector_returns_valid_real_system_metrics() -> None:
    metrics = collect_metrics()

    assert metrics["collected_at"]
    for metric in ("cpu_percent", "ram_percent", "disk_percent"):
        assert 0 <= metrics[metric] <= 100
    for counter in ("net_bytes_sent", "net_bytes_recv", "uptime_seconds"):
        assert metrics[counter] >= 0
