"""
DocuFlow AI — S3 Storage Implementation.

Provides production-ready S3-compatible object storage via boto3,
running blocking I/O calls in an asynchronous thread pool.
"""

from __future__ import annotations

import asyncio
from io import BytesIO
from typing import Any, BinaryIO

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.domain.exceptions import StorageException
from app.infrastructure.storage.base import ObjectStorage


class S3Storage(ObjectStorage):
    """AWS S3 / S3-compatible Object Storage implementation."""

    def __init__(
        self,
        bucket_name: str,
        endpoint_url: str | None = None,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        region_name: str = "us-east-1",
        use_ssl: bool = False,
        s3_force_path_style: bool = True,
    ) -> None:
        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        self.region_name = region_name

        config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path" if s3_force_path_style else "auto"},
            retries={"max_attempts": 3, "mode": "standard"},
        )

        session = boto3.session.Session()
        self._client = session.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=region_name,
            use_ssl=use_ssl,
            config=config,
        )

    def _ensure_bucket_exists(self) -> None:
        """Create bucket if it does not already exist."""
        try:
            self._client.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code in {"404", "NoSuchBucket"}:
                try:
                    if self.region_name and self.region_name != "us-east-1":
                        self._client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={"LocationConstraint": self.region_name},
                        )
                    else:
                        self._client.create_bucket(Bucket=self.bucket_name)
                except Exception as create_err:
                    raise StorageException(f"Failed to create bucket '{self.bucket_name}': {create_err}") from create_err
            else:
                raise StorageException(f"Storage service error accessing bucket '{self.bucket_name}': {e}") from e

    async def upload(
        self,
        key: str,
        data: bytes | BinaryIO,
        content_type: str,
        metadata: dict[str, str] | None = None,
    ) -> str:
        def _sync_upload() -> str:
            try:
                self._ensure_bucket_exists()
                extra_args: dict[str, Any] = {"ContentType": content_type}
                if metadata:
                    extra_args["Metadata"] = metadata

                if isinstance(data, bytes):
                    body: BinaryIO = BytesIO(data)
                else:
                    body = data

                self._client.upload_fileobj(
                    Fileobj=body,
                    Bucket=self.bucket_name,
                    Key=key,
                    ExtraArgs=extra_args,
                )
                return key
            except Exception as e:
                raise StorageException(f"Failed to upload object '{key}' to storage: {e}") from e

        return await asyncio.to_thread(_sync_upload)

    async def download(self, key: str) -> bytes:
        def _sync_download() -> bytes:
            try:
                buffer = BytesIO()
                self._client.download_fileobj(
                    Bucket=self.bucket_name,
                    Key=key,
                    Fileobj=buffer,
                )
                buffer.seek(0)
                return buffer.read()
            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code")
                if error_code in {"404", "NoSuchKey"}:
                    raise StorageException(f"Object '{key}' not found in storage.") from e
                raise StorageException(f"Failed to download object '{key}' from storage: {e}") from e
            except Exception as e:
                raise StorageException(f"Unexpected error downloading object '{key}': {e}") from e

        return await asyncio.to_thread(_sync_download)

    async def delete(self, key: str) -> bool:
        def _sync_delete() -> bool:
            try:
                self._client.delete_object(Bucket=self.bucket_name, Key=key)
                return True
            except Exception as e:
                raise StorageException(f"Failed to delete object '{key}' from storage: {e}") from e

        return await asyncio.to_thread(_sync_delete)

    async def exists(self, key: str) -> bool:
        def _sync_exists() -> bool:
            try:
                self._client.head_object(Bucket=self.bucket_name, Key=key)
                return True
            except ClientError:
                return False
            except Exception as e:
                raise StorageException(f"Failed to check existence for '{key}': {e}") from e

        return await asyncio.to_thread(_sync_exists)

    async def get_presigned_url(self, key: str, expires_in_seconds: int = 3600) -> str:
        def _sync_presign() -> str:
            try:
                url: str = self._client.generate_presigned_url(
                    ClientMethod="get_object",
                    Params={"Bucket": self.bucket_name, "Key": key},
                    ExpiresIn=expires_in_seconds,
                )
                return url
            except Exception as e:
                raise StorageException(f"Failed to generate presigned URL for '{key}': {e}") from e

        return await asyncio.to_thread(_sync_presign)
