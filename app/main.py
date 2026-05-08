"""
Payments API — minimal baseline + notifications service.
"""
from fastapi import FastAPI

from app.routes import notifications

app = FastAPI(title="payments-api", version="0.1.0")

app.include_router(notifications.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/version")
async def version():
    return {"version": app.version}
