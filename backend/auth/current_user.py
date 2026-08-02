# backend/auth/current_user.py
#
# FastAPI dependency that extracts the current user from the JWT cookie.

import logging

import jwt as pyjwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.jwt import COOKIE_NAME, decode_access_token
from backend.config.settings import Settings, get_settings
from backend.database.models import User
from backend.database.postgres import get_db

logger = logging.getLogger(__name__)


async def get_current_user(
    request: Request,
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_db),
) -> User:
    """
    FastAPI dependency: extracts and validates the JWT cookie, returns the User.
    Raises HTTP 401 if not authenticated.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Please sign in with GitHub.",
        )

    if not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_SECRET not configured.",
        )

    try:
        claims = decode_access_token(token, settings.jwt_secret)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired.")
    except pyjwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session.")

    user_id = claims.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token claims.")

    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

    return user


async def get_optional_user(
    request: Request,
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_db),
) -> User | None:
    """
    FastAPI dependency: returns the User if a valid JWT cookie exists, else None.
    Does NOT raise 401 — useful for endpoints that work with or without auth.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token or not settings.jwt_secret:
        return None

    try:
        claims = decode_access_token(token, settings.jwt_secret)
    except pyjwt.PyJWTError:
        return None

    user_id = claims.get("sub")
    if not user_id:
        return None

    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()
