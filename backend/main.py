import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import FRONTEND_DIR, BASE_DIR
from backend.routes.pdf_routes import router as pdf_router
from backend.routes.audiobook_routes import router as audiobook_router
from backend.services.ocr_service import OCRService

app = FastAPI(
    title="PDF to Audiobook Extractor & Converter",
    description="Extracts readable text from PDF documents, detects chapters, and synthesizes natural-sounding audiobooks.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for local client-server flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API endpoints
app.include_router(pdf_router)
app.include_router(audiobook_router)

# OCR Status endpoint
@app.get("/api/ocr/status", tags=["OCR"])
async def get_ocr_status():
    """Check status of extensible OCR subsystem."""
    ocr_service = OCRService(enabled=False)
    return ocr_service.get_status()

# Health check
@app.get("/api/health", tags=["System"])
async def health_check():
    """System health check endpoint."""
    return {
        "status": "healthy",
        "service": "PDF to Audiobook Extractor & Converter",
        "version": "1.0.0"
    }

# Mount static frontend files
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    # Serve index.html at root route
    @app.get("/", include_in_schema=False)
    async def serve_index():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"message": "Frontend not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
