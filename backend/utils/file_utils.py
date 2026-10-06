import os
import re
import uuid
import shutil
from pathlib import Path
from typing import Optional
from backend.config import UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR

def generate_id(prefix: str = "") -> str:
    """Generate a clean, unique ID."""
    uid = uuid.uuid4().hex[:12]
    return f"{prefix}_{uid}" if prefix else uid

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent directory traversal and remove illegal characters.
    """
    # Strip paths
    basename = os.path.basename(filename)
    # Remove null bytes
    basename = basename.replace("\0", "")
    # Keep only alphanumeric, dash, underscore, space, and dot
    clean = re.sub(r'[\\/*?:"<>|]', "", basename).strip()
    if not clean or clean.startswith("."):
        clean = f"document_{clean}" if clean else "document.pdf"
    return clean

def is_pdf_file(filepath: Path) -> bool:
    """Validate that the file begins with standard PDF magic header (%PDF-)."""
    try:
        if not filepath.exists() or filepath.stat().st_size < 5:
            return False
        with open(filepath, "rb") as f:
            header = f.read(5)
            return header.startswith(b"%PDF-")
    except Exception:
        return False

def get_safe_upload_path(file_id: str) -> Optional[Path]:
    """Retrieve verified file path in UPLOAD_DIR, guarding against path traversal."""
    if not file_id or ".." in file_id or "/" in file_id or "\\" in file_id:
        return None
    matches = list(UPLOAD_DIR.glob(f"{file_id}.*")) + list(UPLOAD_DIR.glob(f"{file_id}_*.*"))
    if matches:
        resolved = matches[0].resolve()
        if UPLOAD_DIR.resolve() in resolved.parents:
            return resolved
    return None

def get_output_book_dir(audiobook_id: str) -> Optional[Path]:
    """Return output directory for an audiobook, guarding against path traversal."""
    if not audiobook_id or ".." in audiobook_id or "/" in audiobook_id or "\\" in audiobook_id:
        return None
    target = (OUTPUT_DIR / audiobook_id).resolve()
    if OUTPUT_DIR.resolve() in target.parents or target == OUTPUT_DIR.resolve():
        return target
    return None

def format_size(bytes_count: int) -> str:
    """Human-readable byte size."""
    if bytes_count < 1024:
        return f"{bytes_count} B"
    elif bytes_count < 1024 * 1024:
        return f"{bytes_count / 1024:.1f} KB"
    elif bytes_count < 1024 * 1024 * 1024:
        return f"{bytes_count / (1024 * 1024):.1f} MB"
    else:
        return f"{bytes_count / (1024 * 1024 * 1024):.2f} GB"

def format_duration(seconds: float) -> str:
    """Format seconds into HH:MM:SS or MM:SS."""
    secs = int(seconds)
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def safe_remove_directory(dir_path: Path):
    """Safely remove a directory tree, ignoring errors if locked."""
    try:
        if dir_path.exists() and dir_path.is_dir():
            shutil.rmtree(dir_path, ignore_errors=True)
    except Exception:
        pass
