import os
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

class PDFExtractionError(Exception):
    """Custom exception for PDF extraction issues."""
    pass

class PDFExtractor:
    """Service for extracting text and structure from PDF documents."""

    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"PDF file does not exist: {self.file_path}")
        if fitz is None:
            raise RuntimeError("PyMuPDF library is not installed or failed to initialize.")

    def get_info(self) -> Dict[str, Any]:
        """Read basic metadata and page count without loading entire document."""
        try:
            doc = fitz.open(str(self.file_path))
            page_count = len(doc)
            metadata = doc.metadata or {}
            title = metadata.get("title") or ""
            author = metadata.get("author") or ""
            doc.close()
            return {
                "pages": page_count,
                "title": title.strip() if title else "",
                "author": author.strip() if author else "",
                "file_size": self.file_path.stat().st_size
            }
        except Exception as e:
            raise PDFExtractionError(f"Failed to read PDF metadata: {str(e)}")

    def extract_preview(self, max_preview_pages: int = 5) -> Dict[str, Any]:
        """
        Extract page-wise preview info and detect scanned / image-only PDFs.
        """
        try:
            doc = fitz.open(str(self.file_path))
            total_pages = len(doc)
            preview_pages: List[Dict[str, Any]] = []
            total_extracted_chars = 0
            total_images_found = 0

            pages_to_inspect = min(total_pages, max(max_preview_pages, 3))
            full_preview_snippets = []

            for page_num in range(pages_to_inspect):
                page = doc[page_num]
                text = page.get_text("text") or ""
                images = page.get_images()
                img_count = len(images) if images else 0
                total_images_found += img_count

                stripped_text = text.strip()
                char_count = len(stripped_text)
                total_extracted_chars += char_count

                snippet = stripped_text[:600] + ("..." if len(stripped_text) > 600 else "")
                if stripped_text:
                    full_preview_snippets.append(stripped_text[:1200])

                preview_pages.append({
                    "page_number": page_num + 1,
                    "char_count": char_count,
                    "image_count": img_count,
                    "snippet": snippet,
                    "is_blank": char_count == 0
                })

            doc.close()

            # Scanned detection heuristic:
            # If inspected pages have very few characters (< 40 avg chars) and contain images,
            # or total text is virtually 0 for multi-page documents
            is_scanned = False
            avg_chars = total_extracted_chars / max(1, pages_to_inspect)
            if total_pages > 0 and (total_extracted_chars < 50 or (avg_chars < 30 and total_images_found > 0)):
                is_scanned = True

            combined_preview = "\n\n--- Page Break ---\n\n".join(full_preview_snippets[:3])

            return {
                "total_pages": total_pages,
                "inspected_pages": pages_to_inspect,
                "is_scanned": is_scanned,
                "preview_text": combined_preview,
                "total_extracted_chars_in_sample": total_extracted_chars,
                "pages_info": preview_pages,
                "notice": "This PDF appears to contain scanned images rather than selectable text. OCR is required." if is_scanned else None
            }
        except Exception as e:
            raise PDFExtractionError(f"Preview extraction failed: {str(e)}")

    def extract_all_pages(self) -> List[Dict[str, Any]]:
        """
        Extract text from all pages sequentially without hoarding heavy document handles.
        Returns list of {'page_number': int, 'text': str, 'images_count': int}.
        """
        try:
            doc = fitz.open(str(self.file_path))
            pages_data = []

            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text") or ""
                images = page.get_images()
                pages_data.append({
                    "page_number": page_num + 1,
                    "text": text,
                    "images_count": len(images) if images else 0
                })

            doc.close()
            return pages_data
        except Exception as e:
            raise PDFExtractionError(f"Failed to extract document pages: {str(e)}")
