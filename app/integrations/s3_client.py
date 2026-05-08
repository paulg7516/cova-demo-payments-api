"""S3 client used for KYC document uploads, exported reports, and receipt storage."""
import os
from typing import BinaryIO

import boto3
from botocore.config import Config

_client = None


def get_s3():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
            config=Config(retries={"max_attempts": 3, "mode": "standard"}),
        )
    return _client


def upload_object(bucket: str, key: str, fileobj: BinaryIO, content_type: str | None = None) -> dict:
    extra = {"ContentType": content_type} if content_type else {}
    s3 = get_s3()
    s3.upload_fileobj(fileobj, bucket, key, ExtraArgs=extra)
    return {"bucket": bucket, "key": key}


def presign_put(bucket: str, key: str, content_type: str, expires: int = 900) -> str:
    s3 = get_s3()
    return s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=expires,
    )


def presign_get(bucket: str, key: str, expires: int = 300) -> str:
    s3 = get_s3()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )


def delete_object(bucket: str, key: str) -> None:
    s3 = get_s3()
    s3.delete_object(Bucket=bucket, Key=key)


def head_object(bucket: str, key: str) -> dict:
    s3 = get_s3()
    return s3.head_object(Bucket=bucket, Key=key)
