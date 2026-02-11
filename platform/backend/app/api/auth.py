"""Authentication API routes - signup, login, profile."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.middleware.auth import get_current_customer
from app.models.database import (
    Customer,
    CustomerCreate,
    CustomerLogin,
    CustomerResponse,
    TokenResponse,
)
from app.services.auth import (
    create_access_token,
    customer_to_response,
    hash_password,
    verify_password,
)
from app.services.database import create_customer, get_customer_by_email

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: CustomerCreate):
    """Create a new customer account."""
    # Check if email already exists
    existing = get_customer_by_email(body.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create customer
    pw_hash = hash_password(body.password)
    customer = create_customer(body.email, body.name, pw_hash)

    # Generate JWT
    token = create_access_token(customer.id, customer.email)

    return TokenResponse(
        access_token=token,
        customer=customer_to_response(customer),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: CustomerLogin):
    """Login with email and password."""
    customer = get_customer_by_email(body.email)
    if not customer or not verify_password(body.password, customer.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(customer.id, customer.email)

    return TokenResponse(
        access_token=token,
        customer=customer_to_response(customer),
    )


@router.get("/me", response_model=CustomerResponse)
async def get_profile(customer: Customer = Depends(get_current_customer)):
    """Get current customer profile."""
    return customer_to_response(customer)
