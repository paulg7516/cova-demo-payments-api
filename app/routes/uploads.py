"""File uploads service — KYC documents, receipts, and report downloads via S3."""
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.integrations.s3_client import (
    delete_object,
    head_object,
    presign_get,
    presign_put,
    upload_object,
)

router = APIRouter(prefix="/api/uploads", tags=["uploads"])

KYC_BUCKET = os.environ.get("KYC_BUCKET", "cova-payments-kyc")
RECEIPT_BUCKET = os.environ.get("RECEIPT_BUCKET", "cova-payments-receipts")

ALLOWED_KYC_TYPES = {"image/jpeg", "image/png", "application/pdf"}
MAX_KYC_BYTES = 10 * 1024 * 1024  # 10 MB


class PresignRequest(BaseModel):
    user_id: str
    filename: str
    content_type: str


class PresignResponse(BaseModel):
    upload_url: str
    key: str
    expires_in: int


@router.post("/kyc", response_model=dict)
async def upload_kyc_document(user_id: str, file: UploadFile = File(...)):
    """Direct upload for KYC documents (drivers license, passport, utility bill)."""
    if file.content_type not in ALLOWED_KYC_TYPES:
        raise HTTPException(400, f"Unsupported content type: {file.content_type}")

    contents = await file.read()
    if len(contents) > MAX_KYC_BYTES:
        raise HTTPException(413, "File exceeds 10 MB limit")

    key = f"kyc/{user_id}/{uuid.uuid4().hex}-{file.filename}"
    file.file.seek(0)
    upload_object(KYC_BUCKET, key, file.file, content_type=file.content_type)

    return {
        "uploaded": True,
        "user_id": user_id,
        "bucket": KYC_BUCKET,
        "key": key,
        "size_bytes": len(contents),
        "uploaded_at": datetime.utcnow().isoformat() + "Z",
    }


@router.post("/receipts/presign", response_model=PresignResponse)
async def presign_receipt_upload(req: PresignRequest):
    """Return a presigned URL the client can PUT directly to S3 for large receipts."""
    key = f"receipts/{req.user_id}/{uuid.uuid4().hex}-{req.filename}"
    url = presign_put(RECEIPT_BUCKET, key, req.content_type, expires=900)
    return PresignResponse(upload_url=url, key=key, expires_in=900)


@router.get("/receipts/{key:path}")
async def get_receipt_download_url(key: str):
    """Generate a short-lived download URL for a stored receipt."""
    try:
        head_object(RECEIPT_BUCKET, key)
    except Exception:
        raise HTTPException(404, "Receipt not found")

    url = presign_get(RECEIPT_BUCKET, key, expires=300)
    return {"download_url": url, "expires_in": 300}


@router.delete("/kyc/{user_id}/{key:path}")
async def delete_kyc_document(user_id: str, key: str):
    """Delete a KYC document — used by the GDPR right-to-erasure flow."""
    if not key.startswith(f"kyc/{user_id}/"):
        raise HTTPException(403, "Cannot delete documents owned by another user")
    delete_object(KYC_BUCKET, key)
    return {"deleted": True, "key": key}
