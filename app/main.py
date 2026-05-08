"""
Payments API — checkout, payments, auth, users, refunds.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db import close_pool
from app.routes import admin, auth, checkout, payments, refunds, users


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await close_pool()


app = FastAPI(title="payments-api", version="0.2.0", lifespan=lifespan)

app.include_router(checkout.router)
app.include_router(payments.router)
app.include_router(refunds.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(admin.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/version")
async def version():
    return {"version": app.version}
