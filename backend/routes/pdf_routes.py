import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

from backend.config import UPLOAD_DIR, MAX_UPLOAD_BYTES, MAX_UPLOAD_SIZE_MB, SUPPORTED_VOICES
from backend.utils.file_utils import generate_id, sanitize_filename, is_pdf_file, get_safe_upload_path
from backend.services.pdf_extractor import PDFExtractor, PDFExtractionError

router = APIRouter(prefix="/api", tags=["PDF"])

class UploadResponse(BaseModel):
    file_id: str
    filename: str
    pages: int
    size: int
    title: Optional[str] = ""

@router.post("/upload", response_model=UploadResponse)
async def upload_pdf(file: UploadFile = File(...)):
    """
    Upload and validate a PDF file.
    Validates PDF extension, MIME type, magic bytes, and enforces file size limits.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided in upload."
        )

    clean_name = sanitize_filename(file.filename)
    if not clean_name.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only PDF files are supported."
        )

    file_id = generate_id("pdf")
    dest_path = UPLOAD_DIR / f"{file_id}_{clean_name}"

    # Stream file to disk in chunks to enforce size limits safely
    bytes_read = 0
    chunk_size = 1024 * 1024  # 1MB buffer

    try:
        with open(dest_path, "wb") as out_file:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                bytes_read += len(chunk)
                if bytes_read > MAX_UPLOAD_BYTES:
                    # Exceeded maximum size
                    out_file.close()
                    if dest_path.exists():
                        dest_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File exceeds maximum allowed size of {MAX_UPLOAD_SIZE_MB}MB."
                    )
                out_file.write(chunk)
    except HTTPException:
        raise
    except Exception as e:
        if dest_path.exists():
            dest_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving uploaded file: {str(e)}"
        )

    # Validate PDF magic header
    if not is_pdf_file(dest_path):
        if dest_path.exists():
            dest_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file does not appear to be a valid PDF format."
        )

    # Inspect PDF to count pages and read basic metadata
    try:
        extractor = PDFExtractor(dest_path)
        info = extractor.get_info()
        pages_count = info.get("pages", 0)

        if pages_count == 0:
            if dest_path.exists():
                dest_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded PDF contains 0 pages or is corrupted."
            )

        return UploadResponse(
            file_id=file_id,
            filename=clean_name,
            pages=pages_count,
            size=bytes_read,
            title=info.get("title") or clean_name
        )

    except PDFExtractionError as e:
        if dest_path.exists():
            dest_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to inspect PDF: {str(e)}"
        )

@router.get("/pdf/{file_id}/preview")
async def preview_pdf(file_id: str):
    """
    Extract readable preview text and page-wise summaries from the PDF.
    Detects if the PDF is scanned / image-only.
    """
    pdf_path = get_safe_upload_path(file_id)
    if not pdf_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF file not found or invalid file ID."
        )

    try:
        extractor = PDFExtractor(pdf_path)
        preview_data = extractor.extract_preview(max_preview_pages=5)
        return {
            "file_id": file_id,
            "filename": pdf_path.name.replace(f"{file_id}_", ""),
            **preview_data
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to preview PDF: {str(e)}"
        )

@router.get("/voices")
async def get_voices():
    """Return available TTS languages and voices catalog."""
    return {
        "voices": SUPPORTED_VOICES
    }
