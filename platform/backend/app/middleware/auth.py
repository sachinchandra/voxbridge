"""Authentication middleware and dependencies for FastAPI."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.models.database import Customer
from app.services.auth import decode_token
from app.services.database import get_customer_by_id

security = HTTPBearer()


async def get_current_customer(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Customer:
    """FastAPI dependency: extract and validate the current customer from JWT."""
    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    customer_id = payload.get("sub")
    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    customer = get_customer_by_id(customer_id)
    if customer is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Customer not found",
        )

    return customer


async def get_current_customer_id(
    customer: Customer = Depends(get_current_customer),
) -> str:
    """FastAPI dependency: returns just the customer ID string from JWT."""
    return customer.id
