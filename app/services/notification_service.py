"""
Sends email and SMS notifications.
Swappable: replace SMTP calls with an external provider (SendGrid, AWS SES, etc.)
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from app.config import get_settings
from app.models import Signatory, SignatureRequest

settings = get_settings()


class NotificationService:
    async def send_signing_invitation(
        self, signatory: Signatory, req: SignatureRequest, signing_url: str
    ) -> None:
        subject = f"Prośba o podpis elektroniczny: {req.title}"
        html = self._invitation_html(signatory, req, signing_url)
        await self._send_email(signatory.email, subject, html)

    async def send_reminder(
        self, signatory: Signatory, req: SignatureRequest, signing_url: str
    ) -> None:
        subject = f"Przypomnienie: Oczekujący podpis elektroniczny – {req.title}"
        html = self._reminder_html(signatory, req, signing_url)
        await self._send_email(signatory.email, subject, html)

    async def send_signed_confirmation(self, signatory: Signatory, req: SignatureRequest) -> None:
        subject = f"Potwierdzenie podpisu: {req.title}"
        html = self._signed_html(signatory, req)
        await self._send_email(signatory.email, subject, html)

    async def send_completed_notification(
        self, requester_email: str, req: SignatureRequest
    ) -> None:
        subject = f"Dokument w pełni podpisany: {req.title}"
        html = self._completed_html(req)
        await self._send_email(requester_email, subject, html)

    async def send_otp(self, phone: str, code: str) -> None:
        # Integrate with SMS provider (Twilio, SMSAPI, etc.)
        # Placeholder for real integration
        print(f"[SMS] Send OTP {code} to {phone}")  # noqa: T201

    async def _send_email(self, to: str, subject: str, html: str) -> None:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to
        msg.attach(MIMEText(html, "html", "utf-8"))

        if settings.APP_ENV == "development":
            # In dev, just print — no real SMTP needed
            print(f"[EMAIL] To: {to} | Subject: {subject}")  # noqa: T201
            return

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_TLS:
                server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM, [to], msg.as_string())

    # ── HTML templates ────────────────────────────────────────────────────────

    def _invitation_html(self, signatory: Signatory, req: SignatureRequest, url: str) -> str:
        return f"""
        <div style="font-family:sans-serif;max-width:600px;margin:auto">
          <h2>Zaproszenie do złożenia kwalifikowanego podpisu elektronicznego</h2>
          <p>Witaj {signatory.full_name},</p>
          <p><strong>{req.requester_name or 'Nadawca'}</strong> prosi Cię o złożenie
             <strong>kwalifikowanego podpisu elektronicznego</strong> na dokumencie:</p>
          <blockquote><strong>{req.title}</strong></blockquote>
          {"<p>" + req.message + "</p>" if req.message else ""}
          <p>Poziom podpisu: <strong>{req.signature_level}</strong></p>
          <p style="text-align:center;margin:32px 0">
            <a href="{url}" style="background:#2563EB;color:#fff;padding:14px 28px;
               border-radius:8px;text-decoration:none;font-size:16px">
              Przejdź do podpisu →
            </a>
          </p>
          <p style="color:#6b7280;font-size:12px">
            Link wygaśnie po {req.expires_at.strftime('%d.%m.%Y %H:%M') if req.expires_at else '72 godzinach'}.
            Jeśli nie spodziewałeś się tej wiadomości, zignoruj ją.
          </p>
          <hr style="border:none;border-top:1px solid #e5e7eb">
          <p style="color:#9ca3af;font-size:11px">
            Powered by QSignHub – Kwalifikowane podpisy elektroniczne jako usługa
          </p>
        </div>"""

    def _reminder_html(self, signatory: Signatory, req: SignatureRequest, url: str) -> str:
        return f"""
        <div style="font-family:sans-serif;max-width:600px;margin:auto">
          <h2>Przypomnienie o oczekującym podpisie</h2>
          <p>Witaj {signatory.full_name},</p>
          <p>Dokument <strong>{req.title}</strong> nadal oczekuje na Twój podpis.</p>
          <p style="text-align:center;margin:32px 0">
            <a href="{url}" style="background:#2563EB;color:#fff;padding:14px 28px;
               border-radius:8px;text-decoration:none">Podpisz teraz →</a>
          </p>
        </div>"""

    def _signed_html(self, signatory: Signatory, req: SignatureRequest) -> str:
        return f"""
        <div style="font-family:sans-serif;max-width:600px;margin:auto">
          <h2>✓ Potwierdzenie złożenia podpisu</h2>
          <p>Witaj {signatory.full_name},</p>
          <p>Pomyślnie złożyłeś kwalifikowany podpis elektroniczny na dokumencie
             <strong>{req.title}</strong>.</p>
        </div>"""

    def _completed_html(self, req: SignatureRequest) -> str:
        return f"""
        <div style="font-family:sans-serif;max-width:600px;margin:auto">
          <h2>✓ Dokument w pełni podpisany</h2>
          <p>Wszystkie strony złożyły podpis na dokumencie <strong>{req.title}</strong>.</p>
          <p>Podpisany dokument jest dostępny w panelu QSignHub.</p>
        </div>"""
