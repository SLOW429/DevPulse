import logging
import threading
from contextlib import asynccontextmanager
from math import isfinite
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import agent, alerts, auth, devices, health, realtime
from app.core.config import settings
from app.worker import run_alert_worker


@asynccontextmanager
async def lifespan(_app: FastAPI):
    stop_event = threading.Event()
    worker = None
    if settings.alerts_worker_enabled:
        worker = threading.Thread(
            target=run_alert_worker,
            args=(stop_event,),
            name="devpulse-alert-worker",
            daemon=True,
        )
        worker.start()
    try:
        yield
    finally:
        if worker is not None:
            stop_event.set()
            worker.join(timeout=max(2.0, settings.alert_worker_poll_seconds + 1))


def _json_safe_validation_detail(value: Any) -> Any:
    if isinstance(value, float) and not isfinite(value):
        return repr(value)
    if isinstance(value, dict):
        return {key: _json_safe_validation_detail(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe_validation_detail(item) for item in value]
    return value


app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(_json_safe_validation_detail(exc.errors()))},
    )


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(devices.router)
app.include_router(agent.router)
app.include_router(realtime.router)
app.include_router(alerts.router)