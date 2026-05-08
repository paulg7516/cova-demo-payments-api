"""Authentication — minimal email/password login that issues a session token."""
import secrets
import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from app.db import get_pool

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()


@router.post("/login")
async def login(req: LoginRequest):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, password_salt, password_hash FROM users WHERE email = $1",
            req.email,
        )
    if not row:
        raise HTTPException(401, "invalid credentials")

    if _hash_password(req.password, row["password_salt"]) != row["password_hash"]:
        raise HTTPException(401, "invalid credentials")

    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=12)

    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sessions (user_id, token, expires_at) VALUES ($1, $2, $3)",
            row["id"],
            token,
            expires_at,
        )

    return {"token": token, "expires_at": expires_at.isoformat()}
