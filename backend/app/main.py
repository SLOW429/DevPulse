from fastapi import FastAPI

app = FastAPI(
    title="DevPulse API",
    description="Real-Time Infrastructure Monitoring & Automation Platform",
    version="0.1.0",
)


@app.get("/health")
def health_check() -> dict[str, str]:
    """Simple endpoint to verify that the API is up and running."""
    return {"status": "ok"}