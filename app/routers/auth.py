import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User, Organization
from app.auth import (
    verify_password, hash_password,
    create_access_token, create_refresh_token, decode_token,
)
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse, RegisterRequest
from app.config import get_settings
import re

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:100]


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Create a new organization and owner account."""
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    slug = _slug(payload.organization_name)
    # Ensure slug uniqueness
    count_result = await db.execute(
        select(Organization).where(Organization.slug.like(f"{slug}%"))
    )
    existing_slugs = count_result.scalars().all()
    if existing_slugs:
        slug = f"{slug}-{len(existing_slugs)}"

    org = Organization(
        name=payload.organization_name,
        slug=slug,
        email=payload.email,
    )
    db.add(org)
    await db.flush()

    user = User(
        organization_id=org.id,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role="owner",
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    await db.flush()

    access = create_access_token(str(user.id), str(org.id), user.role)
    refresh = create_refresh_token(str(user.id), str(org.id))
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/token", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()

    access = create_access_token(str(user.id), str(user.organization_id), user.role)
    refresh = create_refresh_token(str(user.id), str(user.organization_id))
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        data = decode_token(payload.refresh_token)
        if data.get("type") != "refresh":
            raise ValueError
        user_id = uuid.UUID(data["sub"])
        org_id = data["org"]
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = await db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    access = create_access_token(str(user.id), org_id, user.role)
    refresh = create_refresh_token(str(user.id), org_id)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
