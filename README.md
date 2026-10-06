# VoiceCraft — PDF to Audiobook Extractor & Converter Studio

A production-ready web application to extract clean text from PDF documents, automatically detect chapter/section structures, and synthesize high-fidelity, natural-sounding audiobooks in MP3 format using neural Text-to-Speech engines (`edge-tts` with `gTTS` fallback).

Includes an in-browser custom audiobook player, background job processing with real-time polling, and individual chapter track downloads.

---

## 🌟 Key Features

* **High-Quality Text Extraction**: Uses PyMuPDF (`fitz`) to extract text and analyze pages without high memory overhead.
* **Intelligent Text Processor**:
  * Strips repeated running headers, footers, and page numbers across pages.
  * Normalizes punctuation (smart quotes, dashes, ellipses).
  * Collapses unnecessary whitespace while preserving paragraph flow.
* **Automatic Chapter & Section Detection**:
  * Detects headings such as `Chapter 1`, `Chapter One`, `CHAPTER I`, `CHAPTER 2: Introduction`, `1. Introduction`, `Prologue`, etc.
  * Graceful fallback: divides documents into logical reading parts if explicit chapter headings are absent.
* **Neural Text-to-Speech**:
  * Powered by Microsoft Edge Neural TTS voices (natural, conversational, emotive).
  * Multi-language support out-of-the-box: English (US, UK, AU), Hindi (Swara & Madhur), Spanish, French, German.
  * Configurable narrator speech rate (0.75x to 2.0x).
  * Automatic `gTTS` fallback if neural TTS service is unreachable.
* **Asynchronous Background Processing**:
  * Background task queue via FastAPI `BackgroundTasks`.
  * Real-time progress updates (Extracting → Structuring → Synthesizing chunks → Mastering MP3).
  * Handles multi-chapter books without blocking the server event loop.
* **Custom In-Browser Audiobook Player**:
  * HTML5 Audio streaming with HTTP range requests for instant scrubbing.
  * Chapter jump selector, Next/Prev chapter buttons, ±10s skips.
  * Dynamic playback speeds (0.75x, 1x, 1.25x, 1.5x, 1.75x, 2x).
  * Audio wave visualizer and keyboard spacebar pause/resume.
* **Chapter Audio Splitting**:
  * Full master audiobook MP3 (`audiobook.mp3`).
  * Individual chapter tracks (`chapter_01.mp3`, `chapter_02.mp3`, etc.).
* **Scanned Document Detection**:
  * Identifies scanned/image-only PDFs and flags them with a clear notice:
    > *"This PDF appears to contain scanned images rather than selectable text. OCR is required."*
* **Extensible OCR Architecture**:
  * Pluggable `ocr_service.py` architecture ready for Tesseract or PaddleOCR integration.
* **Sleek Modern UI**:
  * Pure Vanilla HTML5, CSS3, and JavaScript (Zero React/Node/Tailwind bloat).
  * Dark & Light theme with glowing ambient glassmorphism and smooth micro-animations.

---

## 📁 Project Structure

```text
pdf-audiobook/
│
├── backend/
│   ├── main.py                  # FastAPI application entrypoint & static mount
│   ├── config.py                # Environment configs, paths, and voice catalog
│   ├── requirements.txt         # Python dependencies
│   ├── services/
│   │   ├── pdf_extractor.py     # PyMuPDF text & metadata extraction
│   │   ├── text_processor.py    # Header/footer cleaner, chapter detector, chunker
│   │   ├── tts_service.py       # Edge-TTS neural engine & gTTS fallback
│   │   ├── audio_service.py     # Pure MP3 frame stitcher & pydub/FFmpeg combiner
│   │   ├── ocr_service.py       # Pluggable OCR architectural interface
│   │   └── job_manager.py       # Async job tracking with disk persistence
│   ├── routes/
│   │   ├── pdf_routes.py        # /api/upload, /api/pdf/{id}/preview, /api/voices
│   │   └── audiobook_routes.py  # /api/audiobook/generate, /api/jobs/{id}, downloads
│   └── utils/
│       └── file_utils.py        # Path traversal guard, size/duration formatters
│
├── frontend/
│   ├── index.html               # Semantic HTML5 UI layout
│   ├── style.css                # Custom CSS design system (Dark/Light themes)
│   └── app.js                   # Client controller, polling loop & audio player
│
├── uploads/                     # Secure PDF uploads storage
├── outputs/                     # Generated audiobooks and chapter tracks
├── temp/                        # Ephemeral synthesis chunks (cleaned up automatically)
├── .env                         # Environment configuration
├── .gitignore                   # Git exclusions
└── README.md                    # Project documentation
```

---

## 💻 System Requirements

* **Operating System**: Windows 10/11, macOS, or Linux.
* **Python**: Python 3.11+ (Python 3.11, 3.12, 3.13, 3.14 supported).
* **Optional**: FFmpeg (Recommended for advanced audio mastering, though pure-Python stream concatenation is built-in).

---

## 🛠️ Windows Installation & Setup Guide

### 1. Clone or Open the Project
Open PowerShell or Windows Terminal in the project root:
```powershell
cd "c:\Users\Soumya Ranjan Das\OneDrive\Desktop\pdf to audiobook"
```

### 2. Set Up a Python Virtual Environment (Recommended)
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
*(If PowerShell restricts script execution, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

### 3. Install Dependencies
```powershell
pip install -r backend/requirements.txt
```

> **Note on Windows C++ Runtime**:
> PyMuPDF requires the standard Microsoft Visual C++ 2015-2022 Redistributable (`msvcp140.dll`). If missing on your system, install it via:
> ```powershell
> winget install Microsoft.VCRedist.2015+.x64
> ```

### 4. (Optional) Install FFmpeg on Windows
Although VoiceCraft includes a built-in frame-level MP3 stream combiner that functions without FFmpeg, FFmpeg can be installed via Winget:
```powershell
winget install Gyan.FFmpeg
```
or Scoop:
```powershell
scoop install ffmpeg
```

---

## 🚀 Running the Application

Start the FastAPI application using Uvicorn:

```powershell
uvicorn backend.main:app --reload
```

Then open your browser at:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

* **Interactive Swagger API Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **ReDoc Documentation**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 📡 API Reference

### 1. Document Endpoints

#### `POST /api/upload`
Uploads and validates a PDF document.
* **Request**: `multipart/form-data` with `file: UploadFile`.
* **Response** `200 OK`:
  ```json
  {
    "file_id": "pdf_9c84e1b7",
    "filename": "atomic_habits.pdf",
    "pages": 142,
    "size": 3450120,
    "title": "Atomic Habits"
  }
  ```

#### `GET /api/pdf/{file_id}/preview`
Extracts readable text samples and inspected page breakdowns.
* **Response** `200 OK`:
  ```json
  {
    "file_id": "pdf_9c84e1b7",
    "filename": "atomic_habits.pdf",
    "total_pages": 142,
    "inspected_pages": 5,
    "is_scanned": false,
    "preview_text": "Chapter 1: The Surprising Power of Small Habits...",
    "total_extracted_chars_in_sample": 5420,
    "pages_info": [
      {
        "page_number": 1,
        "char_count": 820,
        "image_count": 0,
        "snippet": "Chapter 1...",
        "is_blank": false
      }
    ],
    "notice": null
  }
  ```

#### `GET /api/voices`
Returns supported narrator voices grouped by language.

---

### 2. Audiobook Synthesis Endpoints

#### `POST /api/audiobook/generate`
Spawns background audiobook conversion pipeline.
* **Request Body**:
  ```json
  {
    "file_id": "pdf_9c84e1b7",
    "language": "en",
    "voice": "en-US-AriaNeural",
    "speed": 1.0,
    "format": "mp3",
    "split_chapters": true
  }
  ```
* **Response** `200 OK`:
  ```json
  {
    "job_id": "job_3a812df0",
    "status": "processing",
    "audiobook_id": "book_e109d93b"
  }
  ```

#### `GET /api/jobs/{job_id}`
Polls progress for an active conversion job.
* **Possible Statuses**: `queued`, `extracting`, `processing`, `generating_audio`, `combining`, `completed`, `failed`.
* **Response** `200 OK`:
  ```json
  {
    "job_id": "job_3a812df0",
    "status": "generating_audio",
    "progress": 55,
    "message": "Synthesizing Chapter 2 (chunk 3/6)...",
    "current_chapter": "Chapter 2: The Four Laws",
    "total_chapters": 12,
    "error": null,
    "audiobook": null
  }
  ```

---

### 3. Audio Playback & Download Endpoints

#### `GET /api/audiobook/{id}/download`
Downloads the complete assembled audiobook MP3.

#### `GET /api/audiobook/{id}/stream`
Streams the master audiobook MP3 with HTTP Range request support for browser seeking.

#### `GET /api/audiobook/{id}/chapters`
Lists all detected chapter tracks with durations and individual download links.

#### `GET /api/audiobook/{id}/chapter/{chapter_number}/download`
Downloads a specific chapter MP3 file.

#### `GET /api/audiobook/{id}/chapter/{chapter_number}/stream`
Streams an individual chapter MP3 file.

---

## 🔍 OCR Architecture & Future Extensibility

VoiceCraft is pre-architected for OCR in `backend/services/ocr_service.py`. When a scanned PDF is uploaded, the app alerts the user without pretending OCR was performed.

To integrate **Tesseract** or **PaddleOCR** in future updates:
1. In `backend/services/ocr_service.py`, set `self.enabled = True`.
2. Implement image extraction from PyMuPDF pixmaps:
   ```python
   pix = page.get_pixmap()
   img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
   text = pytesseract.image_to_string(img)
   ```
3. Return the reconstructed page text dicts. The rest of the cleaning and TTS pipeline works unchanged!

---

## 🛡️ Security & Best Practices

1. **Path Traversal Protection**: All file IDs and routes resolve against verified parent directories using `Path.resolve()`.
2. **File Validation**: Enforces both extension and `%PDF-` binary magic header inspection.
3. **Chunked Streaming**: Uploads stream in 1MB chunks to enforce the 100MB ceiling without RAM spikes.
4. **Automatic Garbage Collection**: Intermediate chunk audio files in `temp/<job_id>` are automatically deleted once the master audiobook and chapters are assembled.

---

## 📜 License

MIT License. Open-source and free for personal and commercial use.
