"""
DocuFlow AI — MinIO Storage Implementation.

MinIO is fully S3 API compatible. This class configures S3Storage
specifically for MinIO local or cluster deployments.
"""

from __future__ import annotations

from app.infrastructure.storage.s3_storage import S3Storage


class MinIOStorage(S3Storage):
    """MinIO Object Storage implementation (S3 compatible with path-style addressing)."""

    def __init__(
        self,
        bucket_name: str,
        endpoint_url: str = "http://localhost:9000",
        access_key: str = "minioadmin",
        secret_key: str = "minioadmin",
        region_name: str = "us-east-1",
        use_ssl: bool = False,
    ) -> None:
        super().__init__(
            bucket_name=bucket_name,
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region_name,
            use_ssl=use_ssl,
            s3_force_path_style=True,
        )
