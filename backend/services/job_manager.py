import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional
from backend.config import TEMP_DIR

class JobManager:
    """Manages asynchronous conversion jobs with in-memory state and disk persistence."""

    def __init__(self):
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._jobs_file = TEMP_DIR / "active_jobs.json"
        self._load_from_disk()

    def _load_from_disk(self):
        try:
            if self._jobs_file.exists():
                with open(self._jobs_file, "r", encoding="utf-8") as f:
                    self._jobs = json.load(f)
        except Exception:
            self._jobs = {}

    def _save_to_disk(self):
        try:
            with open(self._jobs_file, "w", encoding="utf-8") as f:
                json.dump(self._jobs, f, indent=2)
        except Exception:
            pass

    async def create_job(self, job_id: str, file_id: str, audiobook_id: str) -> Dict[str, Any]:
        async with self._lock:
            job_data = {
                "job_id": job_id,
                "file_id": file_id,
                "audiobook_id": audiobook_id,
                "status": "queued",
                "progress": 0,
                "message": "Job queued for processing...",
                "current_chapter": "",
                "total_chapters": 0,
                "error": None,
                "created_at": time.time(),
                "updated_at": time.time(),
                "audiobook": None
            }
            self._jobs[job_id] = job_data
            self._save_to_disk()
            return job_data

    async def update_job(
        self,
        job_id: str,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        current_chapter: Optional[str] = None,
        total_chapters: Optional[int] = None,
        error: Optional[str] = None,
        audiobook: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        async with self._lock:
            if job_id not in self._jobs:
                return None

            job = self._jobs[job_id]
            if status is not None:
                job["status"] = status
            if progress is not None:
                job["progress"] = min(100, max(0, int(progress)))
            if message is not None:
                job["message"] = message
            if current_chapter is not None:
                job["current_chapter"] = current_chapter
            if total_chapters is not None:
                job["total_chapters"] = total_chapters
            if error is not None:
                job["error"] = error
            if audiobook is not None:
                job["audiobook"] = audiobook

            job["updated_at"] = time.time()
            self._save_to_disk()
            return dict(job)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        return self._jobs.get(job_id)

# Global singleton
job_manager = JobManager()
