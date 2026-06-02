import json
import time
from typing import Any, Dict

import httpx
import jwt
from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from jwt.algorithms import RSAAlgorithm

from config import ENTRA_ALLOWED_GROUP_ID, ENTRA_CLIENT_ID, ENTRA_TENANT_ID

JWKS_URL = f"https://login.microsoftonline.com/{ENTRA_TENANT_ID}/discovery/v2.0/keys"
ISSUER = f"https://login.microsoftonline.com/{ENTRA_TENANT_ID}/v2.0"
_JWKS_CACHE: dict[str, Any] = {"keys": None, "expires_at": 0.0}
_ALLOWED_GROUP_IDS = {group_id.strip() for group_id in ENTRA_ALLOWED_GROUP_ID.split(",") if group_id.strip()}


def _mock_user() -> Dict[str, str]:
    return {
        "name": "Development User",
        "email": "dev.user@example.com",
        "oid": "dev-user",
    }


async def _get_jwks(force_refresh: bool = False) -> Dict[str, Any]:
    now = time.time()
    if not force_refresh and _JWKS_CACHE["keys"] and _JWKS_CACHE["expires_at"] > now:
        return _JWKS_CACHE["keys"]

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(JWKS_URL)
        response.raise_for_status()
        jwks = response.json()

    _JWKS_CACHE["keys"] = jwks
    _JWKS_CACHE["expires_at"] = now + 3600
    return jwks


def _get_signing_key(token: str, jwks: Dict[str, Any]):
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")
    if not kid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token header is missing a key identifier.",
        )

    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return RSAAlgorithm.from_jwk(json.dumps(key))

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unable to find a matching signing key.",
    )


def _extract_bearer_token(authorization_header: str | None) -> str:
    if not authorization_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header.",
        )

    scheme, _, token = authorization_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must use the Bearer scheme.",
        )

    return token


def _claims_to_user(claims: Dict[str, Any]) -> Dict[str, str]:
    email = (
        claims.get("preferred_username")
        or claims.get("email")
        or claims.get("upn")
        or "unknown@example.com"
    )
    name = claims.get("name") or email
    return {"name": name, "email": email, "oid": claims.get("oid", "")}


def _require_allowed_group(claims: Dict[str, Any]) -> None:
    if ENTRA_CLIENT_ID == "dev-skip-auth":
        return

    if not _ALLOWED_GROUP_IDS:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Allowed Entra group is not configured.",
        )

    token_groups = claims.get("groups")
    if isinstance(token_groups, str):
        token_groups = [token_groups]

    if not token_groups:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Your token did not include an allowed Entra group.",
        )

    if not set(token_groups).intersection(_ALLOWED_GROUP_IDS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Your account is not in the allowed Entra group.",
        )


async def validate_token(token: str) -> Dict[str, Any]:
    if ENTRA_CLIENT_ID == "dev-skip-auth":
        return {
            "name": _mock_user()["name"],
            "preferred_username": _mock_user()["email"],
            "oid": _mock_user()["oid"],
        }

    jwks = await _get_jwks()
    signing_key = _get_signing_key(token, jwks)

    try:
        return jwt.decode(
            token,
            key=signing_key,
            algorithms=["RS256"],
            audience=ENTRA_CLIENT_ID,
            issuer=ISSUER,
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired.",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is invalid.",
        ) from exc


async def get_current_user(request: Request) -> Dict[str, str]:
    if ENTRA_CLIENT_ID == "dev-skip-auth":
        return _mock_user()

    cached_user = getattr(request.state, "user", None)
    if cached_user:
        return cached_user

    token = _extract_bearer_token(request.headers.get("Authorization"))
    claims = await validate_token(token)
    _require_allowed_group(claims)
    user = _claims_to_user(claims)
    request.state.user = user
    return user


async def auth_middleware(request: Request, call_next):
    path = request.url.path
    if path in {"/", "/health", "/auth-config"} or path.startswith("/static"):
        return await call_next(request)

    if ENTRA_CLIENT_ID == "dev-skip-auth":
        request.state.user = _mock_user()
        return await call_next(request)

    authorization_header = request.headers.get("Authorization")
    if authorization_header:
        try:
            token = _extract_bearer_token(authorization_header)
            claims = await validate_token(token)
            _require_allowed_group(claims)
            request.state.user = _claims_to_user(claims)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
            )

    return await call_next(request)
