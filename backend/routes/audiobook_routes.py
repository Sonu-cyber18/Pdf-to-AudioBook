import json
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.config import OUTPUT_DIR, TEMP_DIR
from backend.utils.file_utils import (
    generate_id,
    get_safe_upload_path,
    get_output_book_dir,
    format_size,
    format_duration,
    safe_remove_directory
)
from backend.services.pdf_extractor import PDFExtractor
from backend.services.text_processor import TextProcessor, ChapterInfo
from backend.services.tts_service import TTSService, TTSError
from backend.services.audio_service import AudioService
from backend.services.job_manager import job_manager

router = APIRouter(prefix="/api", tags=["Audiobook"])

class GenerateAudiobookRequest(BaseModel):
    file_id: str
    language: str = "en"
    voice: str = "en-US-AriaNeural"
    speed: float = Field(default=1.0, ge=0.5, le=2.5)
    format: str = "mp3"
    split_chapters: bool = True

class GenerateAudiobookResponse(BaseModel):
    job_id: str
    status: str
    audiobook_id: str

async def process_audiobook_pipeline(job_id: str, req: GenerateAudiobookRequest, audiobook_id: str):
    """
    Background worker pipeline that executes the full conversion flow:
    1. Extract text from PDF
    2. Clean text & identify chapters
    3. Synthesize speech for all chunks
    4. Combine audio files into chapters and full audiobook
    5. Clean up temporary files
    """
    temp_work_dir = TEMP_DIR / job_id
    out_book_dir = OUTPUT_DIR / audiobook_id

    try:
        pdf_path = get_safe_upload_path(req.file_id)
        if not pdf_path or not pdf_path.exists():
            await job_manager.update_job(
                job_id,
                status="failed",
                error="Uploaded PDF file was not found on server."
            )
            return

        temp_work_dir.mkdir(parents=True, exist_ok=True)
        out_book_dir.mkdir(parents=True, exist_ok=True)

        # -------------------------------------------------------------
        # STEP 1: Text Extraction
        # -------------------------------------------------------------
        await job_manager.update_job(
            job_id,
            status="extracting",
            progress=10,
            message="Extracting text from PDF document..."
        )

        extractor = PDFExtractor(pdf_path)
        doc_info = extractor.get_info()
        raw_pages = extractor.extract_all_pages()

        # Check if text is present or if it's scanned
        total_text_len = sum(len(p["text"].strip()) for p in raw_pages)
        if total_text_len < 30:
            await job_manager.update_job(
                job_id,
                status="failed",
                error="This PDF appears to contain scanned images rather than selectable text. OCR is required."
            )
            return

        # -------------------------------------------------------------
        # STEP 2: Text Cleaning & Chapter Detection
        # -------------------------------------------------------------
        await job_manager.update_job(
            job_id,
            status="processing",
            progress=25,
            message="Analyzing document structure and detecting chapters..."
        )

        processor = TextProcessor()
        cleaned_pages = processor.detect_and_remove_headers_footers(raw_pages)
        chapters: List[ChapterInfo] = processor.detect_chapters(cleaned_pages)

        # Count total TTS chunks
        total_chunks = sum(len(ch.chunks) for ch in chapters)
        if total_chunks == 0:
            await job_manager.update_job(
                job_id,
                status="failed",
                error="No readable content could be prepared for speech synthesis."
            )
            return

        await job_manager.update_job(
            job_id,
            status="generating_audio",
            progress=30,
            total_chapters=len(chapters),
            message=f"Prepared {len(chapters)} chapter(s) with {total_chunks} audio segments."
        )

        # -------------------------------------------------------------
        # STEP 3: TTS Synthesis
        # -------------------------------------------------------------
        completed_chunks = 0
        chapter_audio_map: Dict[int, List[Path]] = {}

        for ch_idx, chapter in enumerate(chapters, 1):
            chapter_chunks_paths: List[Path] = []

            for chunk_idx, chunk_text in enumerate(chapter.chunks, 1):
                msg = f"Synthesizing {chapter.title} (chunk {chunk_idx}/{len(chapter.chunks)})..."
                progress_pct = 30 + int(55 * (completed_chunks / max(1, total_chunks)))

                await job_manager.update_job(
                    job_id,
                    status="generating_audio",
                    progress=progress_pct,
                    message=msg,
                    current_chapter=chapter.title
                )

                chunk_filename = f"ch_{ch_idx:02d}_chunk_{chunk_idx:03d}.mp3"
                chunk_dest = temp_work_dir / chunk_filename

                await TTSService.synthesize_text(
                    text=chunk_text,
                    output_file=chunk_dest,
                    voice=req.voice,
                    language=req.language,
                    speed=req.speed
                )

                chapter_chunks_paths.append(chunk_dest)
                completed_chunks += 1

            chapter_audio_map[ch_idx] = chapter_chunks_paths

        # -------------------------------------------------------------
        # STEP 4: Audio Combining & Metadata Assembly
        # -------------------------------------------------------------
        await job_manager.update_job(
            job_id,
            status="combining",
            progress=88,
            message="Assembling chapter tracks and master audiobook..."
        )

        all_chapter_files: List[Path] = []
        chapters_metadata: List[Dict[str, Any]] = []

        for ch_idx, chapter in enumerate(chapters, 1):
            ch_chunks = chapter_audio_map.get(ch_idx, [])
            ch_dest_file = out_book_dir / f"chapter_{ch_idx:02d}.mp3"

            AudioService.combine_mp3_files(ch_chunks, ch_dest_file)
            all_chapter_files.append(ch_dest_file)

            ch_duration = AudioService.get_mp3_duration(ch_dest_file)
            ch_size = ch_dest_file.stat().st_size

            chapters_metadata.append({
                "chapter_number": ch_idx,
                "title": chapter.title,
                "start_page": chapter.start_page,
                "filename": ch_dest_file.name,
                "download_url": f"/api/audiobook/{audiobook_id}/chapter/{ch_idx}/download",
                "stream_url": f"/api/audiobook/{audiobook_id}/chapter/{ch_idx}/stream",
                "duration_seconds": round(ch_duration, 1),
                "duration_formatted": format_duration(ch_duration),
                "file_size": ch_size,
                "file_size_formatted": format_size(ch_size)
            })

        # Combine all chapters into full audiobook MP3
        master_audiobook_file = out_book_dir / "audiobook.mp3"
        AudioService.combine_mp3_files(all_chapter_files, master_audiobook_file)

        master_duration = AudioService.get_mp3_duration(master_audiobook_file)
        master_size = master_audiobook_file.stat().st_size
        book_title = doc_info.get("title") or pdf_path.name.replace(f"{req.file_id}_", "").replace(".pdf", "")

        metadata = {
            "id": audiobook_id,
            "title": book_title,
            "filename": f"{book_title}.mp3",
            "file_size": master_size,
            "file_size_formatted": format_size(master_size),
            "duration_seconds": round(master_duration, 1),
            "duration_formatted": format_duration(master_duration),
            "voice": req.voice,
            "language": req.language,
            "speed": req.speed,
            "download_url": f"/api/audiobook/{audiobook_id}/download",
            "stream_url": f"/api/audiobook/{audiobook_id}/stream",
            "chapters_count": len(chapters_metadata),
            "chapters": chapters_metadata
        }

        # Save metadata to output directory
        with open(out_book_dir / "metadata.json", "w", encoding="utf-8") as meta_f:
            json.dump(metadata, meta_f, indent=2)

        # -------------------------------------------------------------
        # STEP 5: Finalize and Clean Up
        # -------------------------------------------------------------
        safe_remove_directory(temp_work_dir)

        await job_manager.update_job(
            job_id,
            status="completed",
            progress=100,
            message="Audiobook generated successfully!",
            audiobook=metadata
        )

    except TTSError as tts_err:
        safe_remove_directory(temp_work_dir)
        await job_manager.update_job(
            job_id,
            status="failed",
            error=f"Text-to-Speech Error: {str(tts_err)}"
        )
    except Exception as e:
        safe_remove_directory(temp_work_dir)
        await job_manager.update_job(
            job_id,
            status="failed",
            error=f"Conversion pipeline error: {str(e)}"
        )

@router.post("/audiobook/generate", response_model=GenerateAudiobookResponse)
async def generate_audiobook(
    request: GenerateAudiobookRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger asynchronous audiobook generation.
    Returns immediately with job_id for frontend polling.
    """
    pdf_path = get_safe_upload_path(request.file_id)
    if not pdf_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF file not found. Please upload the file first."
        )

    job_id = generate_id("job")
    audiobook_id = generate_id("book")

    await job_manager.create_job(
        job_id=job_id,
        file_id=request.file_id,
        audiobook_id=audiobook_id
    )

    background_tasks.add_task(
        process_audiobook_pipeline,
        job_id,
        request,
        audiobook_id
    )

    return GenerateAudiobookResponse(
        job_id=job_id,
        status="processing",
        audiobook_id=audiobook_id
    )

@router.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """
    Poll conversion job progress and state.
    """
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found."
        )
    return job

@router.get("/audiobook/{audiobook_id}/download")
async def download_full_audiobook(audiobook_id: str):
    """
    Download the complete assembled audiobook MP3.
    """
    book_dir = get_output_book_dir(audiobook_id)
    if not book_dir or not (book_dir / "audiobook.mp3").exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audiobook file not found."
        )

    # Read title from metadata if available
    download_name = "audiobook.mp3"
    meta_file = book_dir / "metadata.json"
    if meta_file.exists():
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
                download_name = f"{meta.get('title', 'audiobook')}.mp3"
        except Exception:
            pass

    return FileResponse(
        path=str(book_dir / "audiobook.mp3"),
        media_type="audio/mpeg",
        filename=download_name
    )

@router.get("/audiobook/{audiobook_id}/stream")
async def stream_full_audiobook(audiobook_id: str):
    """
    Stream complete audiobook MP3 for in-browser playback with range request seeking.
    """
    book_dir = get_output_book_dir(audiobook_id)
    target = book_dir / "audiobook.mp3" if book_dir else None
    if not target or not target.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audiobook audio stream not found."
        )

    return FileResponse(
        path=str(target),
        media_type="audio/mpeg"
    )

@router.get("/audiobook/{audiobook_id}/chapters")
async def get_audiobook_chapters(audiobook_id: str):
    """
    Get list of chapter details for an audiobook.
    """
    book_dir = get_output_book_dir(audiobook_id)
    if not book_dir:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audiobook not found."
        )

    meta_file = book_dir / "metadata.json"
    if not meta_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audiobook metadata not found."
        )

    with open(meta_file, "r", encoding="utf-8") as f:
        meta = json.load(f)

    return {
        "audiobook_id": audiobook_id,
        "title": meta.get("title", "Audiobook"),
        "chapters": meta.get("chapters", [])
    }

@router.get("/audiobook/{audiobook_id}/chapter/{chapter_number}/download")
async def download_chapter_audio(audiobook_id: str, chapter_number: int):
    """
    Download an individual chapter MP3 file.
    """
    book_dir = get_output_book_dir(audiobook_id)
    if not book_dir:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audiobook not found."
        )

    chapter_file = book_dir / f"chapter_{chapter_number:02d}.mp3"
    if not chapter_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter {chapter_number} audio not found."
        )

    return FileResponse(
        path=str(chapter_file),
        media_type="audio/mpeg",
        filename=f"chapter_{chapter_number:02d}.mp3"
    )

@router.get("/audiobook/{audiobook_id}/chapter/{chapter_number}/stream")
async def stream_chapter_audio(audiobook_id: str, chapter_number: int):
    """
    Stream an individual chapter MP3 for in-browser playback.
    """
    book_dir = get_output_book_dir(audiobook_id)
    if not book_dir:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Audiobook not found."
        )

    chapter_file = book_dir / f"chapter_{chapter_number:02d}.mp3"
    if not chapter_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chapter {chapter_number} audio not found."
        )

    return FileResponse(
        path=str(chapter_file),
        media_type="audio/mpeg"
    )
