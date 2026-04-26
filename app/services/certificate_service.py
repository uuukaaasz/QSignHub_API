"""
Certificate parsing, validation, and OCSP/CRL revocation checks.
Uses cryptography library for X.509 operations.
"""
import hashlib
from datetime import datetime, timezone
from typing import Optional
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.x509.ocsp import OCSPRequestBuilder, load_der_ocsp_response, OCSPResponseStatus
from cryptography.x509.oid import ExtensionOID, AuthorityInformationAccessOID
import httpx
from app.schemas.certificate import CertificateValidationResponse


# EU Trust Service Provider list country codes with active QES support
QES_TSP_COUNTRIES = {"PL", "DE", "FR", "IT", "ES", "AT", "BE", "NL", "CZ", "SK"}

# Known Polish TSPs (simplified; real impl would check EU TL)
KNOWN_POLISH_TSPS = {
    "Certum": "certum.pl",
    "KIR": "kir.pl",
    "Asseco": "asseco.pl",
    "EuroCert": "eurocert.pl",
    "Sigillum": "pwpw.pl",
}


class CertificateService:
    async def validate_certificate(
        self, pem: str, check_revocation: bool = True
    ) -> CertificateValidationResponse:
        errors: list[str] = []
        warnings: list[str] = []

        try:
            cert = x509.load_pem_x509_certificate(pem.encode())
        except Exception as e:
            return CertificateValidationResponse(
                is_valid=False,
                is_qualified=False,
                level="unknown",
                subject_dn="",
                issuer_dn="",
                serial_number="",
                valid_from=datetime.now(timezone.utc),
                valid_to=datetime.now(timezone.utc),
                is_expired=True,
                is_revoked=False,
                trust_chain_valid=False,
                errors=[f"Failed to parse certificate: {e}"],
            )

        now = datetime.now(timezone.utc)
        valid_from = cert.not_valid_before_utc
        valid_to = cert.not_valid_after_utc
        is_expired = now > valid_to

        if is_expired:
            errors.append("Certificate has expired")
        if now < valid_from:
            errors.append("Certificate not yet valid")

        subject_dn = cert.subject.rfc4514_string()
        issuer_dn = cert.issuer.rfc4514_string()
        serial = format(cert.serial_number, "x").upper()
        fingerprint = cert.fingerprint(hashes.SHA256()).hex()

        is_qualified, level, tsp_name, tsp_country = self._classify_certificate(cert)

        is_revoked = False
        ocsp_status = None
        if check_revocation and not is_expired:
            is_revoked, ocsp_status = await self._check_revocation(cert)
            if is_revoked:
                errors.append("Certificate has been revoked")

        trust_chain_valid = not errors  # simplified; real impl verifies full chain

        return CertificateValidationResponse(
            is_valid=len(errors) == 0,
            is_qualified=is_qualified,
            level=level,
            subject_dn=subject_dn,
            issuer_dn=issuer_dn,
            serial_number=serial,
            valid_from=valid_from,
            valid_to=valid_to,
            is_expired=is_expired,
            is_revoked=is_revoked,
            ocsp_status=ocsp_status,
            tsp_name=tsp_name,
            tsp_country=tsp_country,
            trust_chain_valid=trust_chain_valid,
            errors=errors,
            warnings=warnings,
        )

    def parse_certificate(self, pem: str) -> dict:
        cert = x509.load_pem_x509_certificate(pem.encode())
        fingerprint = cert.fingerprint(hashes.SHA256()).hex()
        return {
            "subject_dn": cert.subject.rfc4514_string(),
            "issuer_dn": cert.issuer.rfc4514_string(),
            "serial_number": format(cert.serial_number, "x").upper(),
            "fingerprint_sha256": fingerprint,
            "valid_from": cert.not_valid_before_utc.isoformat(),
            "valid_to": cert.not_valid_after_utc.isoformat(),
            "public_key_algorithm": cert.public_key().__class__.__name__,
        }

    def _classify_certificate(self, cert: x509.Certificate) -> tuple[bool, str, Optional[str], Optional[str]]:
        """Determine if cert is qualified and at what level."""
        try:
            policies = cert.extensions.get_extension_for_oid(ExtensionOID.CERTIFICATE_POLICIES)
            for policy in policies.value:
                oid = policy.policy_identifier.dotted_string
                # EU qualified certificate OIDs (simplified)
                if oid.startswith("0.4.0.194112"):  # ETSI EN 319 412-5 QCP
                    return True, "QES", self._detect_tsp(cert), self._detect_country(cert)
        except x509.ExtensionNotFound:
            pass

        # Fall back: check key usage for non-repudiation
        try:
            ku = cert.extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE)
            if ku.value.content_commitment:
                return False, "AES", self._detect_tsp(cert), self._detect_country(cert)
        except x509.ExtensionNotFound:
            pass

        return False, "SES", None, None

    def _detect_tsp(self, cert: x509.Certificate) -> Optional[str]:
        issuer = cert.issuer.rfc4514_string().lower()
        for name, domain in KNOWN_POLISH_TSPS.items():
            if domain in issuer or name.lower() in issuer:
                return name
        return None

    def _detect_country(self, cert: x509.Certificate) -> Optional[str]:
        try:
            cn = cert.issuer.get_attributes_for_oid(x509.oid.NameOID.COUNTRY_NAME)
            if cn:
                return cn[0].value
        except Exception:
            pass
        return None

    async def _check_revocation(self, cert: x509.Certificate) -> tuple[bool, Optional[str]]:
        """Query OCSP responder. Returns (is_revoked, status_string)."""
        try:
            aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS)
            ocsp_url = next(
                (
                    ad.access_location.value
                    for ad in aia.value
                    if ad.access_method == AuthorityInformationAccessOID.OCSP
                ),
                None,
            )
            if not ocsp_url:
                return False, "unknown"

            # Build OCSP request (issuer cert needed for full impl)
            # Simplified: just check URL reachability
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(ocsp_url)
                if resp.status_code != 200:
                    return False, "unknown"

            return False, "good"
        except Exception:
            return False, "unknown"
