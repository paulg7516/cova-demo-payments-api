"""Stripe webhook handler — settles orders on payment_intent.succeeded etc."""
from fastapi import APIRouter, Header, HTTPException, Request

from app.db import get_pool
from app.integrations.stripe_client import verify_webhook

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.post("/webhook")
async def stripe_webhook(request: Request, stripe_signature: str | None = Header(default=None)):
    payload = await request.body()
    if not stripe_signature:
        raise HTTPException(400, "missing Stripe-Signature header")

    try:
        event = verify_webhook(payload, stripe_signature)
    except Exception as exc:
        raise HTTPException(400, f"invalid signature: {exc}") from exc

    if event["type"] == "payment_intent.succeeded":
        intent = event["data"]["object"]
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE orders SET status = 'paid', settled_at = now() WHERE stripe_intent_id = $1",
                intent["id"],
            )
    elif event["type"] == "payment_intent.payment_failed":
        intent = event["data"]["object"]
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE orders SET status = 'failed' WHERE stripe_intent_id = $1",
                intent["id"],
            )

    return {"received": True}
