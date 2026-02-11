"""Stripe billing API routes.

Handles:
- Creating checkout sessions for plan upgrades
- Stripe webhook processing
- Customer portal for managing subscriptions
- Plan information
"""

from __future__ import annotations

from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.config import settings
from app.middleware.auth import get_current_customer
from app.models.database import Customer, PlanTier
from app.services.database import (
    create_subscription,
    get_active_subscription,
    update_customer_plan,
    update_customer_stripe_id,
)

router = APIRouter(prefix="/billing", tags=["Billing"])

# Configure Stripe
stripe.api_key = settings.stripe_secret_key


# ──────────────────────────────────────────────────────────────────
# Plan information
# ──────────────────────────────────────────────────────────────────

PLANS = [
    {
        "id": "free",
        "name": "Free",
        "price": 0,
        "minutes": settings.free_plan_minutes,
        "max_concurrent": settings.free_max_concurrent_calls,
        "features": [
            f"{settings.free_plan_minutes} minutes/month",
            f"{settings.free_max_concurrent_calls} concurrent calls",
            "All providers supported",
            "Community support",
        ],
    },
    {
        "id": "pro",
        "name": "Pro",
        "price": 49,
        "minutes": settings.pro_plan_minutes,
        "max_concurrent": settings.pro_max_concurrent_calls,
        "features": [
            f"{settings.pro_plan_minutes} minutes/month",
            f"{settings.pro_max_concurrent_calls} concurrent calls",
            "All providers supported",
            "Priority support",
            "Usage analytics",
            "Custom codec support",
        ],
    },
    {
        "id": "enterprise",
        "name": "Enterprise",
        "price": 299,
        "minutes": settings.enterprise_plan_minutes,
        "max_concurrent": settings.enterprise_max_concurrent_calls,
        "features": [
            f"{settings.enterprise_plan_minutes} minutes/month",
            f"{settings.enterprise_max_concurrent_calls} concurrent calls",
            "All providers supported",
            "Dedicated support",
            "Custom SLA",
            "On-prem deployment",
            "SSO / SAML",
        ],
    },
]


@router.get("/plans")
async def get_plans():
    """List available plans."""
    return {"plans": PLANS}


@router.get("/current")
async def get_current_plan(customer: Customer = Depends(get_current_customer)):
    """Get the customer's current plan and subscription status."""
    subscription = get_active_subscription(customer.id)
    plan = next((p for p in PLANS if p["id"] == customer.plan.value), PLANS[0])

    return {
        "plan": plan,
        "subscription": {
            "id": subscription.stripe_subscription_id if subscription else None,
            "status": subscription.status.value if subscription else None,
            "current_period_end": (
                subscription.current_period_end.isoformat()
                if subscription and subscription.current_period_end
                else None
            ),
        } if subscription else None,
    }


# ──────────────────────────────────────────────────────────────────
# Checkout
# ──────────────────────────────────────────────────────────────────

@router.post("/checkout")
async def create_checkout_session(
    body: dict,
    customer: Customer = Depends(get_current_customer),
):
    """Create a Stripe checkout session for plan upgrade."""
    plan = body.get("plan", "pro")

    price_map = {
        "pro": settings.stripe_price_pro,
        "enterprise": settings.stripe_price_enterprise,
    }

    price_id = price_map.get(plan)
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan: {plan}. Choose 'pro' or 'enterprise'.",
        )

    # Create or get Stripe customer
    if not customer.stripe_customer_id:
        stripe_customer = stripe.Customer.create(
            email=customer.email,
            name=customer.name,
            metadata={"voxbridge_customer_id": customer.id},
        )
        update_customer_stripe_id(customer.id, stripe_customer.id)
        stripe_customer_id = stripe_customer.id
    else:
        stripe_customer_id = customer.stripe_customer_id

    # Create checkout session
    session = stripe.checkout.Session.create(
        customer=stripe_customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{settings.frontend_url}/dashboard/billing?success=true",
        cancel_url=f"{settings.frontend_url}/dashboard/billing?canceled=true",
        metadata={"voxbridge_customer_id": customer.id, "plan": plan},
    )

    return {"checkout_url": session.url}


@router.post("/portal")
async def create_portal_session(customer: Customer = Depends(get_current_customer)):
    """Create a Stripe customer portal session for subscription management."""
    if not customer.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No billing account found. Subscribe to a plan first.",
        )

    session = stripe.billing_portal.Session.create(
        customer=customer.stripe_customer_id,
        return_url=f"{settings.frontend_url}/dashboard/billing",
    )

    return {"portal_url": session.url}


# ──────────────────────────────────────────────────────────────────
# Webhook
# ──────────────────────────────────────────────────────────────────

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(data)
    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(data)
    elif event_type == "customer.subscription.deleted":
        _handle_subscription_deleted(data)
    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(data)

    return {"status": "ok"}


def _handle_checkout_completed(session: dict) -> None:
    """Process successful checkout."""
    customer_id = session.get("metadata", {}).get("voxbridge_customer_id")
    plan = session.get("metadata", {}).get("plan", "pro")
    subscription_id = session.get("subscription")

    if not customer_id or not subscription_id:
        return

    plan_tier = PlanTier(plan)
    update_customer_plan(customer_id, plan_tier)

    # Fetch subscription details from Stripe
    sub = stripe.Subscription.retrieve(subscription_id)
    create_subscription(
        customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        plan=plan_tier,
        current_period_start=datetime.fromtimestamp(sub.current_period_start, tz=timezone.utc),
        current_period_end=datetime.fromtimestamp(sub.current_period_end, tz=timezone.utc),
    )


def _handle_subscription_updated(subscription: dict) -> None:
    """Handle subscription updates (plan changes, renewals)."""
    from app.services.database import get_client

    stripe_sub_id = subscription.get("id")
    status_val = subscription.get("status")

    client = get_client()
    result = (
        client.table("subscriptions")
        .select("*")
        .eq("stripe_subscription_id", stripe_sub_id)
        .execute()
    )

    if result.data:
        client.table("subscriptions").update({
            "status": status_val,
            "current_period_start": datetime.fromtimestamp(
                subscription["current_period_start"], tz=timezone.utc
            ).isoformat(),
            "current_period_end": datetime.fromtimestamp(
                subscription["current_period_end"], tz=timezone.utc
            ).isoformat(),
        }).eq("stripe_subscription_id", stripe_sub_id).execute()


def _handle_subscription_deleted(subscription: dict) -> None:
    """Handle subscription cancellation - downgrade to free."""
    from app.services.database import get_client

    stripe_sub_id = subscription.get("id")
    client = get_client()

    result = (
        client.table("subscriptions")
        .select("*")
        .eq("stripe_subscription_id", stripe_sub_id)
        .execute()
    )

    if result.data:
        customer_id = result.data[0]["customer_id"]
        update_customer_plan(customer_id, PlanTier.FREE)

        client.table("subscriptions").update({
            "status": "canceled",
        }).eq("stripe_subscription_id", stripe_sub_id).execute()


def _handle_payment_failed(invoice: dict) -> None:
    """Handle failed payment."""
    from loguru import logger
    logger.warning(f"Payment failed for invoice: {invoice.get('id')}")
