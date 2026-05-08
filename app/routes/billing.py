"""Subscription billing — create / change / cancel plans, invoice history, Stripe webhooks."""
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from app.integrations.stripe_client import (
    cancel_subscription,
    construct_webhook_event,
    create_subscription,
    list_invoices,
    update_subscription_plan,
)

router = APIRouter(prefix="/api/billing", tags=["billing"])


class CreateSubscriptionRequest(BaseModel):
    customer_id: str
    price_id: str
    trial_days: int | None = None


class ChangePlanRequest(BaseModel):
    subscription_id: str
    new_price_id: str


class CancelRequest(BaseModel):
    subscription_id: str
    at_period_end: bool = True


@router.post("/subscriptions")
async def create_sub(req: CreateSubscriptionRequest):
    """Create a new subscription. Returns the latest invoice's payment intent for SCA."""
    try:
        sub = create_subscription(req.customer_id, req.price_id, req.trial_days)
    except Exception as e:
        raise HTTPException(502, f"stripe create failed: {e}")

    pi = ((sub.get("latest_invoice") or {}).get("payment_intent")) or {}
    return {
        "subscription_id": sub["id"],
        "status": sub["status"],
        "client_secret": pi.get("client_secret"),
        "current_period_end": sub.get("current_period_end"),
    }


@router.post("/subscriptions/change-plan")
async def change_plan(req: ChangePlanRequest):
    """Upgrade or downgrade a subscription. Prorates immediately."""
    sub = update_subscription_plan(req.subscription_id, req.new_price_id)
    return {"subscription_id": sub["id"], "status": sub["status"], "items": sub.get("items", {}).get("data", [])}


@router.post("/subscriptions/cancel")
async def cancel(req: CancelRequest):
    """Cancel at period end (default) or immediately."""
    sub = cancel_subscription(req.subscription_id, req.at_period_end)
    return {
        "subscription_id": sub["id"],
        "status": sub["status"],
        "cancel_at_period_end": sub.get("cancel_at_period_end", False),
    }


@router.get("/customers/{customer_id}/invoices")
async def get_invoices(customer_id: str, limit: int = 20):
    """List a customer's recent invoices for the billing portal."""
    invoices = list_invoices(customer_id, limit=min(limit, 100))
    return {"customer_id": customer_id, "count": len(invoices), "invoices": invoices}


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None, alias="Stripe-Signature")):
    """Stripe webhook receiver — handles invoice.payment_failed, customer.subscription.updated, etc."""
    payload = await request.body()
    try:
        event = construct_webhook_event(payload, stripe_signature)
    except Exception as e:
        raise HTTPException(400, f"invalid signature: {e}")

    event_type = event["type"]

    if event_type == "invoice.payment_failed":
        # Dunning: kick off retry sequence
        invoice = event["data"]["object"]
        return {"received": True, "type": event_type, "invoice_id": invoice["id"]}

    if event_type == "customer.subscription.deleted":
        sub = event["data"]["object"]
        return {"received": True, "type": event_type, "subscription_id": sub["id"]}

    return {"received": True, "type": event_type}
