"""
Supabase JWT Authentication Middleware for FastAPI

This module verifies Supabase JWT tokens and extracts the user_id
for use with your local PostgreSQL database.
"""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from core import settings

# Security scheme
security = HTTPBearer(auto_error=False)


def verify_supabase_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> str:
    """
    Verify Supabase JWT token and extract user_id.

    Args:
        credentials: HTTP Bearer token from Authorization header

    Returns:
        str: Supabase user ID (UUID)

    Raises:
        HTTPException: If token is invalid, expired, or missing
    """
    # In development mode, allow requests without auth
    if settings.is_dev() and not settings.SUPABASE_JWT_SECRET:
        # Mock user for development - matches frontend AuthContext mock user
        return "1"

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        # Decode and verify JWT
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET.get_secret_value(),
            algorithms=["HS256"],
            audience="authenticated",  # Supabase uses 'authenticated' audience
        )

        # Extract user ID from 'sub' claim
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID",
            )

        return user_id

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_id(
    user_id: str = Depends(verify_supabase_token)
) -> str:
    """
    Dependency to get the current authenticated user's ID.

    This is the Supabase user.id that you can use to query
    your local PostgreSQL database.

    Usage:
        @router.get("/profile")
        async def get_profile(user_id: str = Depends(get_current_user_id)):
            profile = await student_db_service.load_student_profile(user_id)
            return profile
    """
    return user_id


# Optional: More permissive dependency that doesn't require auth in dev
async def get_current_user_id_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[str]:
    """
    Optional auth dependency - allows requests without auth in development.
    Returns "1" (mock user) if no auth provided in dev mode.
    """
    # If no credentials provided, allow in dev mode
    if not credentials:
        print(f"[AUTH DEBUG] No credentials provided. MODE={settings.MODE}, is_dev={settings.is_dev()}")
        if settings.is_dev():
            print("[AUTH DEBUG] Returning mock user '1' for dev mode")
            return "1"  # Mock user for dev
        print("[AUTH DEBUG] Not in dev mode, returning None")
        return None

    # If credentials provided, verify them
    token = credentials.credentials

    try:
        # Decode and verify JWT
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET.get_secret_value() if settings.SUPABASE_JWT_SECRET else "",
            algorithms=["HS256"],
            audience="authenticated",
        )

        user_id = payload.get("sub")
        if not user_id:
            return None

        return user_id
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
