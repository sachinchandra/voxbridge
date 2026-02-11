"""Authentication service - JWT tokens + password hashing."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import bcrypt
from jose import JWTError, jwt

from app.config import settings
from app.models.database import Customer, CustomerResponse


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a hash."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(customer_id: str, email: str) -> str:
    """Create a JWT access token."""
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expiry_minutes)
    payload = {
        "sub": customer_id,
        "email": email,
        "exp": expires,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT token. Returns payload or None."""
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError:
        return None


def customer_to_response(customer: Customer) -> CustomerResponse:
    """Convert a Customer model to a safe response (no password hash)."""
    return CustomerResponse(
        id=customer.id,
        email=customer.email,
        name=customer.name,
        plan=customer.plan,
        created_at=customer.created_at,
    )
