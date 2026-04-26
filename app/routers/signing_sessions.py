"""
Public signing flow — no API key required, secured by single-use session token.
This is what the browser-based signing UI calls.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.models import SigningSession, Signatory, SignatureRequest
from app.schemas.signing_session import (
    SigningSessionPublic,
    OtpRequest,
    OtpVerify,
    CompleteSigningRequest,
)
from app.schemas.common import SuccessResponse
from app.dependencies import DBSession
from app.auth import generate_otp, hash_otp, verify_otp
from app.services.signature_service import SignatureService
from app.services.notification_service import NotificationService
from app.config import get_settings

settings = get_settings()
router = APIRouter(prefix="/signing-sessions", tags=["Signing Sessions"])

OTP_MAX_ATTEMPTS = 5


async def _get_active_session(token: str, db: DBSession) -> SigningSession:
    result = await db.execute(
        select(SigningSession)
        .where(SigningSession.token == token)
        .options(
            selectinload(SigningSession.signatory),
            selectinload(SigningSession.signature_request),
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signing session not found")
    if session.status != "active":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=f"Session is {session.status}",
        )
    if session.expires_at < datetime.now(timezone.utc):
        session.status = "expired"
        await db.flush()
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Signing session has expired")
    return session


@router.get("/{token}", response_model=SigningSessionPublic)
async def get_signing_session(token: str, db: DBSession):
    """Public endpoint: returns everything the signing UI needs."""
    session = await _get_active_session(token, db)
    sig: Signatory = session.signatory
    req: SignatureRequest = session.signature_request

    # Mark as viewed
    if sig.status == "sent":
        sig.status = "viewed"
        sig.viewed_at = datetime.now(timezone.utc)
        await db.flush()

    return SigningSessionPublic(
        token=session.token,
        status=session.status,
        expires_at=session.expires_at,
        is_completed=session.is_completed,
        requires_otp=sig.identity_verification in ("sms_otp",),
        signatory_name=sig.full_name,
        signatory_email=sig.email,
        request_title=req.title,
        request_message=req.message,
        signature_level=req.signature_level,
        redirect_url=req.redirect_url,
    )


@router.post("/{token}/otp/send", response_model=SuccessResponse)
async def send_otp(token: str, payload: OtpRequest, db: DBSession):
    """Send OTP via SMS or email before signing."""
    session = await _get_active_session(token, db)
    sig: Signatory = session.signatory

    if sig.identity_verification not in ("sms_otp",):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP not required for this signatory")

    code = generate_otp()
    session.otp_code_hash = hash_otp(code)
    session.otp_sent_at = datetime.now(timezone.utc)
    session.otp_attempts = 0
    await db.flush()

    notifier = NotificationService()
    if payload.channel == "sms" and sig.phone:
        await notifier.send_otp(sig.phone, code)
    else:
        # fallback to email
        await notifier.send_otp(sig.email, code)

    return SuccessResponse(message="OTP sent")


@router.post("/{token}/otp/verify", response_model=SuccessResponse)
async def verify_otp_code(token: str, payload: OtpVerify, db: DBSession):
    session = await _get_active_session(token, db)

    if not session.otp_code_hash:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No OTP was requested")

    session.otp_attempts += 1
    if session.otp_attempts > OTP_MAX_ATTEMPTS:
        session.status = "invalidated"
        await db.flush()
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many OTP attempts")

    if not verify_otp(payload.code, session.otp_code_hash):
        await db.flush()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP code")

    session.otp_verified = True
    session.signatory.otp_verified = True
    session.signatory.otp_verified_at = datetime.now(timezone.utc)
    await db.flush()
    return SuccessResponse(message="OTP verified")


@router.post("/{token}/complete", response_model=SuccessResponse)
async def complete_signing(
    token: str,
    payload: CompleteSigningRequest,
    db: DBSession,
    request: Request,
):
    """
    Record the signatory's consent and cryptographic evidence, then mark as signed.
    For QES: payload must contain a valid tsp_token from the external TSP flow.
    """
    session = await _get_active_session(token, db)
    sig: Signatory = session.signatory
    req: SignatureRequest = session.signature_request

    # Guard: OTP required but not verified
    if sig.identity_verification == "sms_otp" and not session.otp_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="OTP verification required")

    if not payload.consent:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Consent must be given to sign")

    # For QES: validate TSP token presence
    if req.signature_level == "QES" and not payload.tsp_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TSP token required for Qualified Electronic Signature",
        )

    ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("User-Agent", "")

    svc = SignatureService(db)
    await svc.complete_signing(session, payload, ip, user_agent)

    return SuccessResponse(
        message="Document signed successfully",
        data={"redirect_url": req.redirect_url},
    )
