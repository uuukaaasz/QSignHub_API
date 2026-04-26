from fastapi import APIRouter, HTTPException, status
from app.schemas.organization import OrganizationResponse, OrganizationUpdate
from app.dependencies import DBSession, AuthUser, AdminUser

router = APIRouter(prefix="/organizations", tags=["Organization"])


@router.get("/me", response_model=OrganizationResponse)
async def get_my_organization(ctx: AuthUser):
    return ctx.organization


@router.patch("/me", response_model=OrganizationResponse)
async def update_my_organization(payload: OrganizationUpdate, db: DBSession, ctx: AdminUser):
    org = ctx.organization
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(org, field, value)
    await db.flush()
    await db.refresh(org)
    return org


@router.get("/me/usage")
async def get_usage(ctx: AuthUser):
    """Return current month's signature consumption vs plan limit."""
    org = ctx.organization
    return {
        "plan": org.plan,
        "monthly_signature_limit": org.monthly_signature_limit,
        "signatures_used_this_month": org.signatures_used_this_month,
        "signatures_remaining": max(0, org.monthly_signature_limit - org.signatures_used_this_month),
        "utilization_pct": round(
            (org.signatures_used_this_month / org.monthly_signature_limit) * 100, 1
        ) if org.monthly_signature_limit else 0,
    }
