"""Refunds — issues Stripe refunds and updates order status."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import get_pool
from app.integrations.stripe_client import issue_refund

router = APIRouter(prefix="/api", tags=["refunds"])


class RefundRequest(BaseModel):
    order_id: int
    amount_cents: int | None = None  # full refund if None
    reason: str | None = None


@router.post("/refunds")
async def create_refund(req: RefundRequest):
    pool = await get_pool()
    async with pool.acquire() as conn:
        order = await conn.fetchrow(
            "SELECT stripe_intent_id, amount_cents, status FROM orders WHERE id = $1",
            req.order_id,
        )

    if not order:
        raise HTTPException(404, "order not found")
    if order["status"] != "paid":
        raise HTTPException(400, f"cannot refund order in status '{order['status']}'")

    refund = issue_refund(order["stripe_intent_id"], req.amount_cents)

    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO refunds (order_id, amount_cents, reason, stripe_refund_id, status)
            VALUES ($1, $2, $3, $4, $5)
            """,
            req.order_id,
            refund.amount,
            req.reason,
            refund.id,
            refund.status,
        )
        await conn.execute(
            "UPDATE orders SET status = 'refunded' WHERE id = $1",
            req.order_id,
        )

    return {"refund_id": refund.id, "amount_cents": refund.amount, "status": refund.status}
