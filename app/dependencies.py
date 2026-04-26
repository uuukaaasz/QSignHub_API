"""
FastAPI dependency injection: authentication, authorization, pagination.
"""
import uuid
from typing import Optional, Annotated
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User, Organization, ApiKey
from app.auth import decode_token, hash_api_key
from app.config import get_settings

settings = get_settings()

bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class CurrentUser:
    def __init__(self, user: User, organization: Organization):
        self.user = user
        self.organization = organization
        self.org_id = organization.id


class ApiKeyContext:
    def __init__(self, api_key: ApiKey, organization: Organization):
        self.api_key = api_key
        self.organization = organization
        self.org_id = organization.id


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise ValueError("Not an access token")
        user_id = uuid.UUID(payload["sub"])
        org_id = uuid.UUID(payload["org"])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    org = await db.get(Organization, org_id)
    if not org or not org.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization inactive")

    return CurrentUser(user=user, organization=org)


async def get_api_key_context(
    raw_key: Optional[str] = Security(api_key_header),
    db: AsyncSession = Depends(get_db),
    request: Request = None,
) -> ApiKeyContext:
    if not raw_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")

    key_hash = hash_api_key(raw_key)
    result = await db.execute(select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True))
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key expired")

    # IP whitelist check
    if api_key.ip_whitelist and request:
        client_ip = request.client.host
        if client_ip not in api_key.ip_whitelist:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="IP not whitelisted")

    org = await db.get(Organization, api_key.organization_id)
    if not org or not org.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization inactive")

    api_key.last_used_at = datetime.now(timezone.utc)
    await db.flush()

    return ApiKeyContext(api_key=api_key, organization=org)


async def require_admin(ctx: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if ctx.user.role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return ctx


class Pagination:
    def __init__(self, page: int = 1, per_page: int = 20):
        self.page = max(1, page)
        self.per_page = min(max(1, per_page), 100)
        self.offset = (self.page - 1) * self.per_page


DBSession = Annotated[AsyncSession, Depends(get_db)]
AuthUser = Annotated[CurrentUser, Depends(get_current_user)]
ApiKeyAuth = Annotated[ApiKeyContext, Depends(get_api_key_context)]
AdminUser = Annotated[CurrentUser, Depends(require_admin)]
Pages = Annotated[Pagination, Depends(Pagination)]
