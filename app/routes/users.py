"""Users — GDPR-style data export endpoint."""
from fastapi import APIRouter, HTTPException

from app.db import get_pool

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/{user_id}/export")
async def export_user_data(user_id: str):
    """Returns the full user record + orders + sessions for GDPR data-subject requests."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT id, email, created_at, country FROM users WHERE id = $1",
            user_id,
        )
        if not user:
            raise HTTPException(404, "user not found")

        orders = await conn.fetch(
            "SELECT id, amount_cents, currency, status, settled_at FROM orders WHERE customer_id = $1",
            user_id,
        )
        sessions = await conn.fetch(
            "SELECT token, expires_at FROM sessions WHERE user_id = $1 ORDER BY expires_at DESC LIMIT 50",
            user_id,
        )

    return {
        "user": dict(user),
        "orders": [dict(o) for o in orders],
        "sessions": [dict(s) for s in sessions],
    }
