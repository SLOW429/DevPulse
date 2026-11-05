from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])
Database = Annotated[Session, Depends(get_db)]


@router.get("/health", response_model=HealthResponse)
def health_check(db: Database) -> HealthResponse:
    """Report readiness only when the database accepts queries."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from None
    return HealthResponse(status="ok")