# backend/api/auth_router.py
#
# GitHub OAuth login + repo management endpoints.
#
# Endpoints:
#   GET  /api/v1/auth/login       — returns GitHub OAuth authorize URL
#   GET  /api/v1/auth/callback    — exchanges code for token, sets JWT cookie
#   GET  /api/v1/auth/me          — returns current user info
#   POST /api/v1/auth/logout      — clears session cookie
#   GET  /api/v1/auth/repos       — list user's GitHub repos
#   POST /api/v1/auth/repos/{owner}/{repo}/activate   — create webhook
#   POST /api/v1/auth/repos/{owner}/{repo}/deactivate — remove webhook

import logging
import secrets
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.current_user import get_current_user
from backend.auth.encryption import decrypt_token, encrypt_token
from backend.auth.jwt import clear_auth_cookie, create_access_token, set_auth_cookie
from backend.auth.oauth import (
    exchange_code_for_token,
    get_github_authorize_url,
    get_github_user,
    list_github_user_repos,
)
from backend.config.settings import Settings, get_settings
from backend.database.models import User, UserRepo
from backend.database.postgres import get_db
from backend.memory.redis_client import redis_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class LoginResponse(BaseModel):
    authorize_url: str


class UserResponse(BaseModel):
    id: str
    github_login: str
    github_avatar_url: str
    email: str | None
    role: str


class RepoResponse(BaseModel):
    full_name: str
    private: bool
    description: str | None
    default_branch: str
    is_active: bool


class ActivateResponse(BaseModel):
    repo_full_name: str
    webhook_id: int | None
    status: str


# ---------------------------------------------------------------------------
# GET /api/v1/auth/login
# ---------------------------------------------------------------------------

@router.get("/login", response_model=LoginResponse)
async def login(settings: Settings = Depends(get_settings)):
    """Return the GitHub OAuth authorize URL. Frontend redirects the browser here."""
    if not settings.github_oauth_client_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GITHUB_OAUTH_CLIENT_ID not configured.",
        )

    # Generate CSRF state token, store in Redis with 10-min TTL
    state = secrets.token_urlsafe(32)
    try:
        if redis_client._client:
            await redis_client._client.setex(f"oauth_state:{state}", 600, "1")
    except Exception:
        # Redis down — accept the CSRF risk for now (dev mode)
        pass

    # OAuth callback goes through localhost (browser redirect, not server-to-server)
    # Webhooks use WEBHOOK_BASE_URL (ngrok) but OAuth doesn't need it
    callback_url = "http://localhost:8001/api/v1/auth/callback"

    authorize_url = get_github_authorize_url(
        client_id=settings.github_oauth_client_id,
        redirect_uri=callback_url,
        state=state,
    )

    return LoginResponse(authorize_url=authorize_url)


# ---------------------------------------------------------------------------
# GET /api/v1/auth/callback
# ---------------------------------------------------------------------------

@router.get("/callback")
async def oauth_callback(
    code: str,
    state: str,
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_db),
):
    """
    GitHub redirects here after the user authorizes.
    Exchanges code for token, upserts User, sets JWT cookie, redirects to frontend.
    """
    # 1. Verify CSRF state (best-effort — if Redis is down, skip check)
    try:
        if redis_client._client:
            stored = await redis_client._client.get(f"oauth_state:{state}")
            if not stored:
                raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")
            await redis_client._client.delete(f"oauth_state:{state}")
    except HTTPException:
        raise
    except Exception:
        pass  # Redis down — skip CSRF check in dev

    # 2. Exchange code for GitHub access token
    try:
        access_token = await exchange_code_for_token(
            code=code,
            client_id=settings.github_oauth_client_id,
            client_secret=settings.github_oauth_client_secret,
        )
    except (ValueError, httpx.HTTPError) as e:
        logger.error("OAuth token exchange failed: %s", e)
        raise HTTPException(status_code=400, detail=f"GitHub OAuth failed: {e}")

    # 3. Fetch GitHub user profile
    try:
        gh_user = await get_github_user(access_token)
    except httpx.HTTPError as e:
        logger.error("Failed to fetch GitHub user: %s", e)
        raise HTTPException(status_code=400, detail="Failed to fetch GitHub profile.")

    github_id = gh_user["id"]
    github_login = gh_user["login"]
    avatar_url = gh_user.get("avatar_url", "")
    email = gh_user.get("email")

    # 4. Encrypt the access token before storing
    encrypted_token = encrypt_token(access_token, settings.jwt_secret)

    # 5. Upsert user in DB
    result = await session.execute(select(User).where(User.github_id == github_id))
    user = result.scalar_one_or_none()

    if user:
        # Update existing user
        user.github_login = github_login
        user.github_avatar_url = avatar_url
        user.github_access_token_encrypted = encrypted_token
        user.email = email or user.email
        user.last_login_at = datetime.now(timezone.utc)
    else:
        # Create new user
        user = User(
            github_id=github_id,
            github_login=github_login,
            github_avatar_url=avatar_url,
            github_access_token_encrypted=encrypted_token,
            email=email,
            role="reviewer",
            last_login_at=datetime.now(timezone.utc),
        )
        session.add(user)

    await session.commit()
    await session.refresh(user)

    # 6. Create JWT and set cookie
    jwt_token = create_access_token(
        user_id=user.id,
        github_login=user.github_login,
        role=user.role,
        secret=settings.jwt_secret,
        expiry_hours=settings.jwt_expiry_hours,
    )

    redirect_url = f"{settings.frontend_url}/repos"
    response = RedirectResponse(url=redirect_url, status_code=302)
    set_auth_cookie(response, jwt_token, max_age_hours=settings.jwt_expiry_hours)

    logger.info("oauth_callback | user=%s login=%s | redirect to %s", user.id, github_login, redirect_url)
    return response


# ---------------------------------------------------------------------------
# GET /api/v1/auth/me
# ---------------------------------------------------------------------------

@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """Return the current authenticated user's info."""
    return UserResponse(
        id=user.id,
        github_login=user.github_login,
        github_avatar_url=user.github_avatar_url,
        email=user.email,
        role=user.role,
    )


# ---------------------------------------------------------------------------
# POST /api/v1/auth/logout
# ---------------------------------------------------------------------------

@router.post("/logout")
async def logout():
    """Clear the session cookie."""
    response = RedirectResponse(url="/login", status_code=302)
    clear_auth_cookie(response)
    return response


# ---------------------------------------------------------------------------
# GET /api/v1/auth/repos
# ---------------------------------------------------------------------------

@router.get("/repos", response_model=list[RepoResponse])
async def list_repos(
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_db),
):
    """List the user's GitHub repos with their activation status."""
    # Decrypt the user's GitHub token
    access_token = decrypt_token(user.github_access_token_encrypted, settings.jwt_secret)

    # Fetch repos from GitHub
    try:
        gh_repos = await list_github_user_repos(access_token)
    except httpx.HTTPError as e:
        logger.error("Failed to fetch repos for user %s: %s", user.github_login, e)
        raise HTTPException(status_code=502, detail="Failed to fetch repos from GitHub.")

    # Get which repos are active in our DB
    result = await session.execute(
        select(UserRepo).where(UserRepo.user_id == user.id, UserRepo.is_active == 1)
    )
    active_repos = {r.repo_full_name for r in result.scalars().all()}

    return [
        RepoResponse(
            full_name=r["full_name"],
            private=r["private"],
            description=r.get("description"),
            default_branch=r.get("default_branch", "main"),
            is_active=r["full_name"] in active_repos,
        )
        for r in gh_repos
    ]


# ---------------------------------------------------------------------------
# POST /api/v1/auth/repos/{owner}/{repo}/activate
# ---------------------------------------------------------------------------

@router.post("/repos/{owner}/{repo}/activate", response_model=ActivateResponse)
async def activate_repo(
    owner: str,
    repo: str,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_db),
):
    """Create a webhook on the repo and start monitoring it."""
    repo_full_name = f"{owner}/{repo}"
    access_token = decrypt_token(user.github_access_token_encrypted, settings.jwt_secret)

    # Generate a per-repo webhook secret
    webhook_secret = secrets.token_hex(32)

    # Determine our webhook callback URL
    if not settings.webhook_base_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="WEBHOOK_BASE_URL not configured in .env",
        )
    webhook_url = f"{settings.webhook_base_url}/webhook/github"

    # Create webhook on GitHub
    webhook_id = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"https://api.github.com/repos/{repo_full_name}/hooks",
                json={
                    "name": "web",
                    "active": True,
                    "events": ["pull_request"],
                    "config": {
                        "url": webhook_url,
                        "content_type": "json",
                        "secret": webhook_secret,
                        "insecure_ssl": "0",
                    },
                },
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
            if resp.status_code == 422:
                # Webhook might already exist
                logger.warning("Webhook may already exist for %s: %s", repo_full_name, resp.text)
            else:
                resp.raise_for_status()
                webhook_id = resp.json().get("id")
    except httpx.HTTPError as e:
        logger.error("Failed to create webhook for %s: %s", repo_full_name, e)
        raise HTTPException(status_code=502, detail=f"Failed to create webhook: {e}")

    # Upsert user_repos row
    result = await session.execute(
        select(UserRepo).where(
            UserRepo.user_id == user.id,
            UserRepo.repo_full_name == repo_full_name,
        )
    )
    user_repo = result.scalar_one_or_none()

    if user_repo:
        user_repo.is_active = 1
        user_repo.webhook_id = webhook_id or user_repo.webhook_id
        user_repo.webhook_secret = webhook_secret
    else:
        user_repo = UserRepo(
            user_id=user.id,
            repo_full_name=repo_full_name,
            is_active=1,
            webhook_id=webhook_id,
            webhook_secret=webhook_secret,
        )
        session.add(user_repo)

    await session.commit()

    logger.info(
        "repo_activated | user=%s repo=%s webhook_id=%s",
        user.github_login, repo_full_name, webhook_id,
    )

    return ActivateResponse(
        repo_full_name=repo_full_name,
        webhook_id=webhook_id,
        status="active",
    )


# ---------------------------------------------------------------------------
# POST /api/v1/auth/repos/{owner}/{repo}/deactivate
# ---------------------------------------------------------------------------

@router.post("/repos/{owner}/{repo}/deactivate", response_model=ActivateResponse)
async def deactivate_repo(
    owner: str,
    repo: str,
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_db),
):
    """Remove the webhook and stop monitoring the repo."""
    repo_full_name = f"{owner}/{repo}"

    # Find the user_repo entry
    result = await session.execute(
        select(UserRepo).where(
            UserRepo.user_id == user.id,
            UserRepo.repo_full_name == repo_full_name,
        )
    )
    user_repo = result.scalar_one_or_none()

    if not user_repo:
        raise HTTPException(status_code=404, detail="Repo not found in your monitored repos.")

    # Delete webhook from GitHub
    if user_repo.webhook_id:
        access_token = decrypt_token(user.github_access_token_encrypted, settings.jwt_secret)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.delete(
                    f"https://api.github.com/repos/{repo_full_name}/hooks/{user_repo.webhook_id}",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/json",
                    },
                )
                if resp.status_code not in (204, 404):
                    resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning("Failed to delete webhook for %s: %s", repo_full_name, e)

    # Deactivate in DB
    user_repo.is_active = 0
    await session.commit()

    logger.info("repo_deactivated | user=%s repo=%s", user.github_login, repo_full_name)

    return ActivateResponse(
        repo_full_name=repo_full_name,
        webhook_id=None,
        status="inactive",
    )
