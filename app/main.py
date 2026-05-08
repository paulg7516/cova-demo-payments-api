"""
Payments API — minimal baseline.

The main branch only exposes uptime/version probes. Real business
endpoints get added in feature branches so Cova's PR Guard has
clear diffs to flag.
"""
from fastapi import FastAPI

app = FastAPI(title="payments-api", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/version")
async def version():
    return {"version": app.version}
