import asyncio
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.websocket_tickets import (
    consume_websocket_ticket,
    issue_websocket_ticket,
)
from app.models.user import User
from app.schemas.dashboard import DashboardSnapshot, WebSocketTicket
from app.services.dashboard_service import get_dashboard_snapshot

router = APIRouter(tags=["Realtime"])


@router.post("/realtime/ticket", response_model=WebSocketTicket)
def create_websocket_ticket(
    user: Annotated[User, Depends(get_current_user)],
) -> WebSocketTicket:
    ticket, expires_in = issue_websocket_ticket(user.id)
    return WebSocketTicket(ticket=ticket, expires_in=expires_in)


@router.get("/dashboard", response_model=DashboardSnapshot)
def read_dashboard(
    user: Annotated[User, Depends(get_current_user)],
    db: Session = Depends(get_db),
) -> DashboardSnapshot:
    snapshot = get_dashboard_snapshot(db, user.id)
    if snapshot is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is no longer active",
        )
    return snapshot


@router.websocket("/ws/dashboard")
async def dashboard_updates(
    websocket: WebSocket,
    ticket: str = Query(min_length=20, max_length=128),
    db: Session = Depends(get_db),
) -> None:
    origin = websocket.headers.get("origin")
    if origin is not None and origin not in settings.frontend_origins:
        await websocket.close(code=4403, reason="Websocket origin not allowed")
        return
    user_id = consume_websocket_ticket(ticket)
    if user_id is None:
        await websocket.close(code=4401, reason="Invalid or expired websocket ticket")
        return

    await websocket.accept()
    try:
        while True:
            db.expire_all()
            snapshot = await asyncio.to_thread(
                get_dashboard_snapshot,
                db,
                user_id,
            )
            if snapshot is None:
                await websocket.close(code=4401, reason="User is no longer active")
                return
            await websocket.send_json(snapshot.model_dump(mode="json"))
            await asyncio.to_thread(db.close)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return
