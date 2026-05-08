"""Checkout — initiates Stripe payment intents and writes orders to Postgres."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import get_pool
from app.integrations.stripe_client import create_payment_intent

router = APIRouter(prefix="/api", tags=["checkout"])


class CheckoutRequest(BaseModel):
    customer_id: str
    cart_total_cents: int
    currency: str = "usd"


@router.post("/checkout")
async def create_checkout(req: CheckoutRequest):
    if req.cart_total_cents <= 0:
        raise HTTPException(400, "cart_total_cents must be positive")

    pool = await get_pool()
    intent = create_payment_intent(
        amount_cents=req.cart_total_cents,
        currency=req.currency,
        customer_id=req.customer_id,
    )

    async with pool.acquire() as conn:
        order_id = await conn.fetchval(
            """
            INSERT INTO orders (customer_id, amount_cents, currency, stripe_intent_id, status)
            VALUES ($1, $2, $3, $4, 'pending')
            RETURNING id
            """,
            req.customer_id,
            req.cart_total_cents,
            req.currency,
            intent.id,
        )

    return {
        "order_id": order_id,
        "client_secret": intent.client_secret,
        "amount_cents": req.cart_total_cents,
    }
