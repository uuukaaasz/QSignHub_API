import hashlib
import uuid
import os
from datetime import timedelta
from typing import BinaryIO, Optional
import aioboto3
from app.config import get_settings

settings = get_settings()


class StorageService:
    def __init__(self):
        self._session = aioboto3.Session()

    def _client(self):
        return self._session.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
        )

    async def upload_document(
        self, file_data: bytes, filename: str, mime_type: str, org_id: uuid.UUID
    ) -> tuple[str, str]:
        """Upload raw document. Returns (storage_key, checksum_sha256)."""
        checksum = hashlib.sha256(file_data).hexdigest()
        key = f"orgs/{org_id}/documents/{uuid.uuid4()}/{filename}"

        async with self._client() as s3:
            await s3.put_object(
                Bucket=settings.S3_BUCKET_DOCUMENTS,
                Key=key,
                Body=file_data,
                ContentType=mime_type,
                Metadata={"checksum-sha256": checksum},
            )
        return key, checksum

    async def upload_signed_document(
        self, file_data: bytes, org_id: uuid.UUID, filename: str
    ) -> str:
        """Upload signed document. Returns storage_key."""
        key = f"orgs/{org_id}/signed/{uuid.uuid4()}/{filename}"
        async with self._client() as s3:
            await s3.put_object(
                Bucket=settings.S3_BUCKET_SIGNED,
                Key=key,
                Body=file_data,
                ContentType="application/pdf",
            )
        return key

    async def generate_presigned_url(
        self, bucket: str, key: str, expires_in: int = 3600, filename: Optional[str] = None
    ) -> str:
        """Generate a time-limited pre-signed download URL."""
        params: dict = {"Bucket": bucket, "Key": key}
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

        async with self._client() as s3:
            url = await s3.generate_presigned_url(
                "get_object", Params=params, ExpiresIn=expires_in
            )
        return url

    async def download(self, bucket: str, key: str) -> bytes:
        async with self._client() as s3:
            resp = await s3.get_object(Bucket=bucket, Key=key)
            return await resp["Body"].read()

    async def delete(self, bucket: str, key: str) -> None:
        async with self._client() as s3:
            await s3.delete_object(Bucket=bucket, Key=key)
