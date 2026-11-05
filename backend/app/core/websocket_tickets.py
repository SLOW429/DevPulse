from datetime import UTC, datetime, timedelta
import hashlib
import secrets
from threading import Lock

_TICKET_LIFETIME_SECONDS = 30
_tickets: dict[str, tuple[int, datetime]] = {}
_tickets_lock = Lock()


def issue_websocket_ticket(user_id: int) -> tuple[str, int]:
    ticket = secrets.token_urlsafe(32)
    ticket_hash = hashlib.sha256(ticket.encode("ascii")).hexdigest()
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=_TICKET_LIFETIME_SECONDS)
    with _tickets_lock:
        _purge_expired(now)
        _tickets[ticket_hash] = (user_id, expires_at)
    return ticket, _TICKET_LIFETIME_SECONDS


def consume_websocket_ticket(ticket: str) -> int | None:
    ticket_hash = hashlib.sha256(ticket.encode("utf-8")).hexdigest()
    now = datetime.now(UTC)
    with _tickets_lock:
        _purge_expired(now)
        stored = _tickets.pop(ticket_hash, None)
    if stored is None:
        return None
    user_id, expires_at = stored
    return user_id if expires_at > now else None


def _purge_expired(now: datetime) -> None:
    expired = [key for key, (_, deadline) in _tickets.items() if deadline <= now]
    for key in expired:
        del _tickets[key]
