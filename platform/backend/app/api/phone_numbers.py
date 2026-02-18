"""Phone number management API routes.

Provision, list, reassign, and release phone numbers via Twilio.
Numbers are assigned to agents to handle inbound/outbound calls.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from app.config import settings
from app.middleware.auth import get_current_customer
from app.models.database import (
    Customer,
    PhoneNumberBuyRequest,
    PhoneNumberResponse,
    PhoneNumberSearchRequest,
    PhoneNumberSearchResult,
    PhoneNumberUpdate,
)
from app.services.database import (
    assign_phone_number,
    count_phone_numbers,
    create_phone_number,
    get_agent,
    get_phone_number,
    list_phone_numbers,
    release_phone_number,
)

router = APIRouter(prefix="/phone-numbers", tags=["Phone Numbers"])

# Plan-based phone number limits
_PHONE_LIMITS = {
    "free": 1,
    "pro": 10,
    "enterprise": 100,
}


def _phone_to_response(phone, agent_name: str = "") -> PhoneNumberResponse:
    """Convert a PhoneNumber model to a PhoneNumberResponse."""
    return PhoneNumberResponse(
        id=phone.id,
        phone_number=phone.phone_number,
        provider=phone.provider,
        country=phone.country,
        capabilities=phone.capabilities,
        status=phone.status,
        agent_id=phone.agent_id,
        agent_name=agent_name,
        created_at=phone.created_at,
    )


# ──────────────────────────────────────────────────────────────────
# Search Available Numbers
# ──────────────────────────────────────────────────────────────────

@router.post("/search", response_model=list[PhoneNumberSearchResult])
async def search_available_numbers(
    body: PhoneNumberSearchRequest,
    customer: Customer = Depends(get_current_customer),
):
    """Search for available phone numbers to buy.

    Uses Twilio's API to search for available numbers by country,
    area code, or pattern match.
    """
    try:
        from twilio.rest import Client as TwilioClient

        twilio = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)

        # Build search params
        search_kwargs: dict = {"limit": body.limit}
        if body.area_code:
            search_kwargs["area_code"] = body.area_code
        if body.contains:
            search_kwargs["contains"] = body.contains

        # Search by country
        if body.country == "US":
            available = twilio.available_phone_numbers("US").local.list(**search_kwargs)
        elif body.country == "GB":
            available = twilio.available_phone_numbers("GB").local.list(**search_kwargs)
        elif body.country == "CA":
            available = twilio.available_phone_numbers("CA").local.list(**search_kwargs)
        else:
            available = twilio.available_phone_numbers(body.country).local.list(**search_kwargs)

        results = []
        for number in available:
            capabilities = []
            if getattr(number, "capabilities", {}).get("voice"):
                capabilities.append("voice")
            if getattr(number, "capabilities", {}).get("sms"):
                capabilities.append("sms")

            results.append(PhoneNumberSearchResult(
                phone_number=number.phone_number,
                friendly_name=getattr(number, "friendly_name", number.phone_number),
                country=body.country,
                region=getattr(number, "region", ""),
                capabilities=capabilities or ["voice"],
                monthly_cost_cents=100,  # ~$1/month for US local
            ))

        return results

    except ImportError:
        # Twilio not installed — return mock data for development
        logger.warning("Twilio SDK not installed, returning mock phone numbers")
        return [
            PhoneNumberSearchResult(
                phone_number=f"+1555010{i:04d}",
                friendly_name=f"(555) 010-{i:04d}",
                country=body.country,
                region="CA",
                capabilities=["voice"],
                monthly_cost_cents=100,
            )
            for i in range(body.limit)
        ]
    except Exception as e:
        logger.error(f"Twilio search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to search phone numbers: {str(e)}",
        )


# ──────────────────────────────────────────────────────────────────
# Buy a Phone Number
# ──────────────────────────────────────────────────────────────────

@router.post("/buy", response_model=PhoneNumberResponse, status_code=status.HTTP_201_CREATED)
async def buy_phone_number(
    body: PhoneNumberBuyRequest,
    customer: Customer = Depends(get_current_customer),
):
    """Buy (provision) a phone number and add it to the account.

    Optionally assign to an agent at purchase time.
    """
    # Check phone number limit for plan
    current_count = count_phone_numbers(customer.id)
    limit = _PHONE_LIMITS.get(customer.plan.value, 1)
    if current_count >= limit:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Phone number limit reached ({limit}) for your {customer.plan.value} plan. Upgrade to add more numbers.",
        )

    # Validate agent exists if specified
    agent_name = ""
    if body.agent_id:
        agent = get_agent(body.agent_id, customer.id)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found",
            )
        agent_name = agent.name

    # Provision via Twilio
    provider_sid = ""
    try:
        from twilio.rest import Client as TwilioClient

        twilio = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)

        # Configure webhook URL for inbound calls
        webhook_url = f"{settings.twilio_webhook_base_url}/api/v1/webhooks/twilio/inbound"
        status_url = f"{settings.twilio_webhook_base_url}/api/v1/webhooks/twilio/status"

        incoming = twilio.incoming_phone_numbers.create(
            phone_number=body.phone_number,
            voice_url=webhook_url,
            voice_method="POST",
            status_callback=status_url,
            status_callback_method="POST",
        )
        provider_sid = incoming.sid
        logger.info(f"Provisioned Twilio number {body.phone_number} → SID: {provider_sid}")

    except ImportError:
        logger.warning("Twilio SDK not installed, using mock SID")
        provider_sid = f"PN_mock_{body.phone_number[-4:]}"
    except Exception as e:
        logger.error(f"Twilio provisioning error: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to provision phone number: {str(e)}",
        )

    # Store in database
    phone = create_phone_number({
        "customer_id": customer.id,
        "phone_number": body.phone_number,
        "agent_id": body.agent_id,
        "provider": "twilio",
        "provider_sid": provider_sid,
        "country": "US",
        "capabilities": ["voice"],
        "status": "active",
    })

    return _phone_to_response(phone, agent_name)


# ──────────────────────────────────────────────────────────────────
# List Phone Numbers
# ──────────────────────────────────────────────────────────────────

@router.get("", response_model=list[PhoneNumberResponse])
async def list_customer_phone_numbers(
    customer: Customer = Depends(get_current_customer),
):
    """List all active phone numbers for the current customer."""
    phones = list_phone_numbers(customer.id)

    # Build agent name cache
    agent_names: dict[str, str] = {}
    for phone in phones:
        if phone.agent_id and phone.agent_id not in agent_names:
            agent = get_agent(phone.agent_id, customer.id)
            agent_names[phone.agent_id] = agent.name if agent else "Unknown"

    return [
        _phone_to_response(p, agent_names.get(p.agent_id, "") if p.agent_id else "")
        for p in phones
    ]


# ──────────────────────────────────────────────────────────────────
# Get Single Phone Number
# ──────────────────────────────────────────────────────────────────

@router.get("/{phone_id}", response_model=PhoneNumberResponse)
async def get_phone_number_by_id(
    phone_id: str,
    customer: Customer = Depends(get_current_customer),
):
    """Get a single phone number by ID."""
    phone = get_phone_number(phone_id, customer.id)
    if not phone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found",
        )

    agent_name = ""
    if phone.agent_id:
        agent = get_agent(phone.agent_id, customer.id)
        agent_name = agent.name if agent else "Unknown"

    return _phone_to_response(phone, agent_name)


# ──────────────────────────────────────────────────────────────────
# Update (Reassign) Phone Number
# ──────────────────────────────────────────────────────────────────

@router.patch("/{phone_id}", response_model=PhoneNumberResponse)
async def update_phone_number(
    phone_id: str,
    body: PhoneNumberUpdate,
    customer: Customer = Depends(get_current_customer),
):
    """Update a phone number — reassign to a different agent or unassign."""
    # Verify phone number exists
    existing = get_phone_number(phone_id, customer.id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found",
        )

    # Validate new agent if specified
    agent_name = ""
    if body.agent_id:
        agent = get_agent(body.agent_id, customer.id)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found",
            )
        agent_name = agent.name

    updated = assign_phone_number(phone_id, customer.id, body.agent_id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update phone number",
        )

    return _phone_to_response(updated, agent_name)


# ──────────────────────────────────────────────────────────────────
# Release Phone Number
# ──────────────────────────────────────────────────────────────────

@router.delete("/{phone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def release_phone_number_endpoint(
    phone_id: str,
    customer: Customer = Depends(get_current_customer),
):
    """Release a phone number — removes from Twilio and marks as released."""
    # Verify phone number exists
    phone = get_phone_number(phone_id, customer.id)
    if not phone:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Phone number not found",
        )

    # Release from Twilio
    try:
        from twilio.rest import Client as TwilioClient

        if phone.provider_sid and not phone.provider_sid.startswith("PN_mock_"):
            twilio = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
            twilio.incoming_phone_numbers(phone.provider_sid).delete()
            logger.info(f"Released Twilio number {phone.phone_number} (SID: {phone.provider_sid})")
    except ImportError:
        logger.warning("Twilio SDK not installed, skipping Twilio release")
    except Exception as e:
        logger.error(f"Twilio release error: {e}")
        # Continue with DB release even if Twilio fails

    # Mark as released in DB
    success = release_phone_number(phone_id, customer.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to release phone number",
        )
