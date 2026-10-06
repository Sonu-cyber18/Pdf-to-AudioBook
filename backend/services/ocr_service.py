from pathlib import Path
from typing import List, Dict, Any, Optional

class OCRService:
    """
    Extensible OCR Service Architecture.
    Designed to easily plug in Tesseract, PaddleOCR, or EasyOCR in future iterations.
    Currently disabled by default as specified in design requirements.
    """

    def __init__(self, enabled: bool = False, engine: str = "tesseract"):
        self.enabled = enabled
        self.engine = engine

    def is_available(self) -> bool:
        """Check if OCR runtime dependencies are installed and enabled."""
        if not self.enabled:
            return False
        # Future check for pytesseract, paddleocr etc.
        return False

    def get_status(self) -> Dict[str, Any]:
        """Return current OCR system status and setup instructions."""
        return {
            "enabled": self.enabled,
            "engine": self.engine,
            "available": self.is_available(),
            "supported_engines": ["tesseract", "paddleocr"],
            "setup_note": (
                "OCR is currently disabled. To enable OCR support, install Tesseract OCR "
                "or PaddleOCR and enable OCR in configuration."
            )
        }

    def extract_text_from_scanned_pdf(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """
        Pluggable method to run OCR over scanned PDF pages.
        Raises NotImplementedError if invoked while OCR remains disabled.
        """
        if not self.enabled:
            raise NotImplementedError(
                "OCR is currently disabled. Please configure Tesseract or PaddleOCR to process scanned documents."
            )

        # Hook point for future integration:
        # 1. Render PDF pages to images using PyMuPDF (page.get_pixmap())
        # 2. Pass images through PaddleOCR or pytesseract.image_to_string()
        # 3. Return page-wise text dicts
        return []
