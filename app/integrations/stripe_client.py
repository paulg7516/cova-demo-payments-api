"""Stripe client wrapper for recurring billing — subscriptions, invoices, webhooks."""
import os

import stripe

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")


def create_subscription(customer_id: str, price_id: str, trial_days: int | None = None) -> dict:
    params: dict = {
        "customer": customer_id,
        "items": [{"price": price_id}],
        "payment_behavior": "default_incomplete",
        "expand": ["latest_invoice.payment_intent"],
    }
    if trial_days:
        params["trial_period_days"] = trial_days
    return stripe.Subscription.create(**params).to_dict()


def cancel_subscription(subscription_id: str, at_period_end: bool = True) -> dict:
    if at_period_end:
        return stripe.Subscription.modify(subscription_id, cancel_at_period_end=True).to_dict()
    return stripe.Subscription.delete(subscription_id).to_dict()


def update_subscription_plan(subscription_id: str, new_price_id: str) -> dict:
    sub = stripe.Subscription.retrieve(subscription_id)
    item_id = sub["items"]["data"][0]["id"]
    return stripe.Subscription.modify(
        subscription_id,
        items=[{"id": item_id, "price": new_price_id}],
        proration_behavior="create_prorations",
    ).to_dict()


def list_invoices(customer_id: str, limit: int = 20) -> list[dict]:
    res = stripe.Invoice.list(customer=customer_id, limit=limit)
    return [inv.to_dict() for inv in res["data"]]


def construct_webhook_event(payload: bytes, sig_header: str):
    return stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
