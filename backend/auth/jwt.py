# backend/auth/jwt.py
#
# JWT token creation and verification for user sessions.
# Uses HS256 symmetric signing with the app's JWT_SECRET.

import logging
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Response

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
COOKIE_NAME = "session_token"


def create_access_token(
    user_id: str,
    github_login: str,
    role: str,
    secret: str,
    expiry_hours: int = 24,
) -> str:
    """Create an HS256-signed JWT with user claims."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "login": github_login,
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=expiry_hours),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, secret: str) -> dict:
    """Decode and verify a JWT. Raises jwt.PyJWTError on failure."""
    return jwt.decode(token, secret, algorithms=[ALGORITHM])


def set_auth_cookie(response: Response, token: str, max_age_hours: int = 24) -> None:
    """Set an httpOnly session cookie on the response."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,  # Set to True in production behind HTTPS
        samesite="lax",
        max_age=max_age_hours * 3600,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    """Clear the session cookie."""
    response.delete_cookie(key=COOKIE_NAME, path="/")
