"""Notifications service — email, SMS, preferences, history."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from app.integrations.redis_client import already_sent, queue_notification
from app.integrations.sendgrid_client import send_email
from app.integrations.twilio_client import send_sms

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class EmailRequest(BaseModel):
    user_id: str
    to: EmailStr
    subject: str
    html: str
    idempotency_key: str | None = None


class SmsRequest(BaseModel):
    user_id: str
    to: str
    body: str
    idempotency_key: str | None = None


class PreferencesRequest(BaseModel):
    user_id: str
    email_enabled: bool = True
    sms_enabled: bool = False
    marketing_enabled: bool = False


@router.post("/email")
async def send_email_notification(req: EmailRequest):
    if req.idempotency_key and await already_sent(req.idempotency_key):
        return {"status": "duplicate", "key": req.idempotency_key}

    status = send_email(req.to, req.subject, req.html)
    if status >= 400:
        raise HTTPException(502, f"sendgrid returned {status}")

    await queue_notification(req.user_id, {"channel": "email", "to": req.to, "subject": req.subject})
    return {"status": "sent", "provider_status": status}


@router.post("/sms")
async def send_sms_notification(req: SmsRequest):
    if req.idempotency_key and await already_sent(req.idempotency_key):
        return {"status": "duplicate", "key": req.idempotency_key}

    sid = send_sms(req.to, req.body)
    await queue_notification(req.user_id, {"channel": "sms", "to": req.to, "sid": sid})
    return {"status": "sent", "sid": sid}


@router.get("/{user_id}")
async def list_notifications(user_id: str, limit: int = 50):
    """Returns the most recent N notifications queued for this user."""
    from app.integrations.redis_client import get_redis

    r = get_redis()
    items = await r.lrange(f"notif:queue:{user_id}", 0, max(0, limit - 1))
    return {"user_id": user_id, "count": len(items), "items": items}


@router.post("/preferences")
async def update_preferences(req: PreferencesRequest):
    """Update a user's notification channel preferences."""
    from app.integrations.redis_client import get_redis

    r = get_redis()
    await r.hset(
        f"notif:prefs:{req.user_id}",
        mapping={
            "email_enabled": "1" if req.email_enabled else "0",
            "sms_enabled": "1" if req.sms_enabled else "0",
            "marketing_enabled": "1" if req.marketing_enabled else "0",
        },
    )
    return {"updated": True}
