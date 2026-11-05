import logging
import signal
import threading

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.alert_service import (
    dispatch_due_notifications,
    evaluate_offline_rules,
    evaluate_pending_metrics,
)

logger = logging.getLogger(__name__)

WORKERS = (
    evaluate_pending_metrics,
    evaluate_offline_rules,
    dispatch_due_notifications,
)


def run_alert_worker(stop_event: threading.Event) -> None:
    while not stop_event.wait(max(0.2, settings.alert_worker_poll_seconds)):
        with SessionLocal() as db:
            for worker in WORKERS:
                try:
                    worker(db)
                except Exception as exc:
                    db.rollback()
                    logger.error(
                        "alert_worker_task_failed",
                        extra={
                            "task": worker.__name__,
                            "error_type": type(exc).__name__,
                        },
                    )


def main() -> None:
    stop_event = threading.Event()

    def request_shutdown(_signal: int, _frame: object) -> None:
        stop_event.set()

    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)
    run_alert_worker(stop_event)


if __name__ == "__main__":
    main()
