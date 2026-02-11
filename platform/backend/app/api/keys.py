"""API Key management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.middleware.auth import get_current_customer
from app.models.database import (
    ApiKeyCreate,
    ApiKeyCreatedResponse,
    ApiKeyResponse,
    Customer,
)
from app.services.database import (
    create_api_key,
    get_api_keys_for_customer,
    revoke_api_key,
)

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


@router.post("", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_key(
    body: ApiKeyCreate,
    customer: Customer = Depends(get_current_customer),
):
    """Create a new API key. The full key is only returned once."""
    # Limit number of keys
    existing = get_api_keys_for_customer(customer.id)
    active = [k for k in existing if k.status == "active"]
    if len(active) >= 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 active API keys allowed",
        )

    api_key, full_key = create_api_key(customer.id, body.name)

    return ApiKeyCreatedResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        key=full_key,
        status=api_key.status,
        last_used_at=api_key.last_used_at,
        created_at=api_key.created_at,
    )


@router.get("", response_model=list[ApiKeyResponse])
async def list_keys(customer: Customer = Depends(get_current_customer)):
    """List all API keys for the current customer."""
    keys = get_api_keys_for_customer(customer.id)
    return [
        ApiKeyResponse(
            id=k.id,
            name=k.name,
            key_prefix=k.key_prefix,
            status=k.status,
            last_used_at=k.last_used_at,
            created_at=k.created_at,
        )
        for k in keys
    ]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_key(
    key_id: str,
    customer: Customer = Depends(get_current_customer),
):
    """Revoke an API key."""
    success = revoke_api_key(key_id, customer.id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found",
        )
