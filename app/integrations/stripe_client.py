"""Stripe SDK initialization. Used by checkout, refunds, and webhook handlers."""
import os

import stripe

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
STRIPE_WEBHOOK_SECRET = os.environ["STRIPE_WEBHOOK_SECRET"]


def create_payment_intent(amount_cents: int, currency: str = "usd", customer_id: str | None = None):
    return stripe.PaymentIntent.create(
        amount=amount_cents,
        currency=currency,
        customer=customer_id,
        automatic_payment_methods={"enabled": True},
    )


def issue_refund(charge_id: str, amount_cents: int | None = None):
    kwargs = {"charge": charge_id}
    if amount_cents is not None:
        kwargs["amount"] = amount_cents
    return stripe.Refund.create(**kwargs)


def verify_webhook(payload: bytes, signature_header: str):
    return stripe.Webhook.construct_event(payload, signature_header, STRIPE_WEBHOOK_SECRET)
