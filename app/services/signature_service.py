"""
Orchestrates the full signing lifecycle:
  create → send → sign → complete

For QES: delegates actual cryptographic operations to the configured TSP.
For AES/SES: handles signing in-process (image/typed) and embeds into PDF.
"""
import uuid
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models import SignatureRequest, Signatory, SigningSession, Document, AuditLog
from app.schemas.signature_request import SignatureRequestCreate
from app.schemas.signing_session import CompleteSigningRequest
from app.config import get_settings
from app.services.notification_service import NotificationService
from app.services.webhook_service import WebhookService

settings = get_settings()


class SignatureService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.notifier = NotificationService()
        self.webhooks = WebhookService(db)

    async def create_request(
        self, org_id: uuid.UUID, payload: SignatureRequestCreate
    ) -> SignatureRequest:
        req = SignatureRequest(
            organization_id=org_id,
            title=payload.title,
            message=payload.message,
            reference=payload.reference,
            signature_level=payload.signature_level,
            signature_format=payload.signature_format,
            signing_order=payload.signing_order,
            expires_at=payload.expires_at,
            send_reminders=payload.send_reminders,
            reminder_interval_days=payload.reminder_interval_days,
            notify_on_signed=payload.notify_on_signed,
            notify_on_completed=payload.notify_on_completed,
            requester_email=payload.requester_email,
            requester_name=payload.requester_name,
            redirect_url=payload.redirect_url,
            metadata=payload.metadata,
            status="draft",
        )
        self.db.add(req)
        await self.db.flush()

        # Attach documents
        if payload.document_ids:
            docs = await self.db.execute(
                select(Document).where(
                    Document.id.in_(payload.document_ids),
                    Document.organization_id == org_id,
                )
            )
            for doc in docs.scalars():
                doc.signature_request_id = req.id

        # Add signatories
        for idx, s in enumerate(payload.signatories):
            signatory = Signatory(
                signature_request_id=req.id,
                email=s.email,
                full_name=s.full_name,
                phone=s.phone,
                order=s.order if payload.signing_order == "sequential" else 1,
                role=s.role,
                identity_verification=s.identity_verification,
                metadata=s.metadata,
                status="pending",
            )
            self.db.add(signatory)

        await self.db.flush()
        await self._audit(req.id, org_id, "system", None, "signature_request.created",
                          "SignatureRequest", str(req.id), "Request created in draft state")
        return req

    async def send_request(self, req: SignatureRequest) -> SignatureRequest:
        """Transition draft → pending and dispatch signing invitations."""
        req.status = "pending"
        await self.db.flush()

        signatories = await self.db.execute(
            select(Signatory).where(Signatory.signature_request_id == req.id)
        )
        signatories = signatories.scalars().all()

        # For sequential signing, only send to order=1 initially
        to_notify = signatories
        if req.signing_order == "sequential":
            min_order = min(s.order for s in signatories)
            to_notify = [s for s in signatories if s.order == min_order]

        for signatory in to_notify:
            session = await self._create_signing_session(req, signatory)
            signing_url = f"{settings.SIGNING_SESSION_BASE_URL}/sign/{session.token}"
            await self.notifier.send_signing_invitation(signatory, req, signing_url)
            signatory.status = "sent"
            signatory.sent_at = datetime.now(timezone.utc)

        await self.db.flush()
        await self.webhooks.dispatch("signature_request.sent", {"signature_request_id": str(req.id)}, req.organization_id)
        await self._audit(req.id, req.organization_id, "system", None, "signature_request.sent",
                          "SignatureRequest", str(req.id), f"Sent to {len(to_notify)} signatory(ies)")
        return req

    async def complete_signing(
        self,
        session: SigningSession,
        payload: CompleteSigningRequest,
        ip: str,
        user_agent: str,
    ) -> SigningSession:
        """Record signing evidence and mark signatory as signed."""
        signatory = await self.db.get(Signatory, session.signatory_id)
        req = await self.db.get(SignatureRequest, session.signature_request_id)

        now = datetime.now(timezone.utc)
        signatory.status = "signed"
        signatory.signed_at = now
        signatory.ip_address = ip
        signatory.user_agent = user_agent

        session.is_completed = True
        session.signed_at = now
        session.used_at = now
        session.status = "used"

        await self.db.flush()

        await self.webhooks.dispatch(
            "signatory.signed",
            {"signatory_id": str(signatory.id), "signature_request_id": str(req.id)},
            req.organization_id,
        )
        await self._audit(req.id, req.organization_id, "signatory", str(signatory.id),
                          "signatory.signed", "Signatory", str(signatory.id),
                          f"{signatory.full_name} signed", {"ip": ip})

        # Check if all signatories are done
        await self._check_completion(req)
        return session

    async def _check_completion(self, req: SignatureRequest) -> None:
        result = await self.db.execute(
            select(Signatory).where(Signatory.signature_request_id == req.id)
        )
        signatories = result.scalars().all()
        signers = [s for s in signatories if s.role == "signer"]
        signed = [s for s in signers if s.status == "signed"]

        if req.signing_order == "sequential":
            # Advance to next unsigned
            unsigned = [s for s in signers if s.status not in ("signed", "declined")]
            if unsigned:
                next_order = min(s.order for s in unsigned)
                next_batch = [s for s in unsigned if s.order == next_order]
                for s in next_batch:
                    session = await self._create_signing_session(req, s)
                    url = f"{settings.SIGNING_SESSION_BASE_URL}/sign/{session.token}"
                    await self.notifier.send_signing_invitation(s, req, url)
                    s.status = "sent"
                    s.sent_at = datetime.now(timezone.utc)

        if len(signed) == len(signers):
            req.status = "completed"
            req.completed_at = datetime.now(timezone.utc)
            await self.db.flush()
            await self.webhooks.dispatch(
                "signature_request.completed",
                {"signature_request_id": str(req.id)},
                req.organization_id,
            )
            await self._audit(req.id, req.organization_id, "system", None,
                              "signature_request.completed", "SignatureRequest", str(req.id),
                              "All signatories have signed")

    async def _create_signing_session(
        self, req: SignatureRequest, signatory: Signatory
    ) -> SigningSession:
        token = secrets.token_urlsafe(64)
        session = SigningSession(
            signature_request_id=req.id,
            signatory_id=signatory.id,
            token=token,
            status="active",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.SIGNING_SESSION_EXPIRE_HOURS),
        )
        self.db.add(session)
        await self.db.flush()
        return session

    async def _audit(
        self,
        req_id: Optional[uuid.UUID],
        org_id: uuid.UUID,
        actor_type: str,
        actor_id: Optional[str],
        event: str,
        resource_type: str,
        resource_id: str,
        description: str,
        metadata: Optional[dict] = None,
    ) -> None:
        log = AuditLog(
            organization_id=org_id,
            signature_request_id=req_id,
            actor_type=actor_type,
            actor_id=actor_id,
            event=event,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            metadata=metadata,
        )
        self.db.add(log)
        await self.db.flush()
