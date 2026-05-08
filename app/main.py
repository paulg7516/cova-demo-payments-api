"""
Payments API — minimal baseline + file uploads service.
"""
from fastapi import FastAPI

from app.routes import uploads

app = FastAPI(title="payments-api", version="0.1.0")

app.include_router(uploads.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/version")
async def version():
    return {"version": app.version}
