# backend/auth/oauth.py
#
# GitHub OAuth helpers — builds authorize URL, exchanges code for token,
# fetches user profile from GitHub API.

import logging
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_USER_REPOS_URL = "https://api.github.com/user/repos"


def get_github_authorize_url(
    client_id: str,
    redirect_uri: str,
    state: str,
) -> str:
    """Build the GitHub OAuth authorization URL."""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "repo read:user user:email",
        "state": state,
    }
    return f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code_for_token(
    code: str,
    client_id: str,
    client_secret: str,
) -> str:
    """Exchange an OAuth code for a GitHub access token."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()

    if "error" in data:
        logger.error("GitHub OAuth error: %s — %s", data["error"], data.get("error_description"))
        raise ValueError(f"GitHub OAuth error: {data['error']}")

    return data["access_token"]


async def get_github_user(access_token: str) -> dict:
    """Fetch the authenticated GitHub user's profile."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            GITHUB_USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def list_github_user_repos(
    access_token: str,
    page: int = 1,
    per_page: int = 100,
) -> list[dict]:
    """Fetch repos the authenticated user has access to."""
    repos = []
    async with httpx.AsyncClient(timeout=15.0) as client:
        while True:
            resp = await client.get(
                GITHUB_USER_REPOS_URL,
                params={
                    "per_page": per_page,
                    "page": page,
                    "sort": "updated",
                    "direction": "desc",
                    "affiliation": "owner,collaborator,organization_member",
                },
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            repos.extend(batch)
            if len(batch) < per_page:
                break
            page += 1
    return repos
