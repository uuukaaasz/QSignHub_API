import uuid
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, func
from app.models import ApiKey
from app.schemas.api_key import ApiKeyCreate, ApiKeyResponse, ApiKeyCreatedResponse
from app.schemas.common import PaginatedResponse
from app.auth import generate_api_key
from app.dependencies import DBSession, AuthUser, AdminUser, Pages
import math

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


@router.get("", response_model=PaginatedResponse[ApiKeyResponse])
async def list_api_keys(db: DBSession, ctx: AuthUser, pagination: Pages):
    total = await db.scalar(
        select(func.count()).select_from(ApiKey).where(ApiKey.organization_id == ctx.org_id)
    )
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.organization_id == ctx.org_id)
        .order_by(ApiKey.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.per_page)
    )
    keys = result.scalars().all()
    return PaginatedResponse(
        data=keys,
        total=total,
        page=pagination.page,
        per_page=pagination.per_page,
        pages=math.ceil(total / pagination.per_page) if total else 0,
    )


@router.post("", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(payload: ApiKeyCreate, db: DBSession, ctx: AdminUser):
    raw_key, key_hash = generate_api_key(payload.environment)
    prefix = raw_key[:20]  # e.g. qsh_live_XXXXXX

    api_key = ApiKey(
        organization_id=ctx.org_id,
        name=payload.name,
        key_hash=key_hash,
        key_prefix=prefix,
        environment=payload.environment,
        scopes=payload.scopes,
        ip_whitelist=payload.ip_whitelist,
        expires_at=payload.expires_at,
        description=payload.description,
        is_active=True,
    )
    db.add(api_key)
    await db.flush()

    resp = ApiKeyCreatedResponse.model_validate(api_key)
    resp.key = raw_key
    return resp


@router.get("/{key_id}", response_model=ApiKeyResponse)
async def get_api_key(key_id: uuid.UUID, db: DBSession, ctx: AuthUser):
    key = await db.get(ApiKey, key_id)
    if not key or key.organization_id != ctx.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    return key


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(key_id: uuid.UUID, db: DBSession, ctx: AdminUser):
    key = await db.get(ApiKey, key_id)
    if not key or key.organization_id != ctx.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API key not found")
    key.is_active = False
    await db.flush()
