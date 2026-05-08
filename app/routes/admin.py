"""Admin — privileged operations: user impersonation and hard-delete."""
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException

from app.db import get_pool

router = APIRouter(prefix="/api/admin", tags=["admin"])


async def _require_admin(authorization: str | None) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u.id, u.is_admin
            FROM sessions s JOIN users u ON u.id = s.user_id
            WHERE s.token = $1 AND s.expires_at > now()
            """,
            token,
        )
    if not row or not row["is_admin"]:
        raise HTTPException(403, "admin only")
    return row["id"]


@router.post("/users/{user_id}/impersonate")
async def impersonate_user(user_id: str, authorization: str | None = Header(default=None)):
    """Mints a session token belonging to another user. Audit-logged."""
    admin_id = await _require_admin(authorization)

    pool = await get_pool()
    async with pool.acquire() as conn:
        target = await conn.fetchrow("SELECT id, email FROM users WHERE id = $1", user_id)
        if not target:
            raise HTTPException(404, "user not found")

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        await conn.execute(
            "INSERT INTO sessions (user_id, token, expires_at, impersonated_by) VALUES ($1, $2, $3, $4)",
            user_id,
            token,
            expires_at,
            admin_id,
        )
        await conn.execute(
            "INSERT INTO audit_log (actor_id, action, target_id, metadata) VALUES ($1, 'impersonate', $2, '{}')",
            admin_id,
            user_id,
        )

    return {"token": token, "expires_at": expires_at.isoformat(), "impersonating": target["email"]}


@router.delete("/users/{user_id}")
async def hard_delete_user(user_id: str, authorization: str | None = Header(default=None)):
    """Cascading hard-delete of a user and all related orders, refunds, and sessions."""
    admin_id = await _require_admin(authorization)

    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute("DELETE FROM sessions WHERE user_id = $1", user_id)
            await conn.execute("DELETE FROM refunds WHERE order_id IN (SELECT id FROM orders WHERE customer_id = $1)", user_id)
            await conn.execute("DELETE FROM orders WHERE customer_id = $1", user_id)
            deleted = await conn.fetchval("DELETE FROM users WHERE id = $1 RETURNING id", user_id)
            await conn.execute(
                "INSERT INTO audit_log (actor_id, action, target_id, metadata) VALUES ($1, 'hard_delete_user', $2, '{}')",
                admin_id,
                user_id,
            )

    if not deleted:
        raise HTTPException(404, "user not found")
    return {"deleted": True, "user_id": user_id}
