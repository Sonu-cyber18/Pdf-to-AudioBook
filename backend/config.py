import os
from pathlib import Path
from dotenv import load_dotenv

# Find project root (one level above backend/)
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env file if it exists
dotenv_path = BASE_DIR / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)

# Directories
UPLOAD_DIR = BASE_DIR / os.getenv("UPLOAD_DIR", "uploads")
OUTPUT_DIR = BASE_DIR / os.getenv("OUTPUT_DIR", "outputs")
TEMP_DIR = BASE_DIR / os.getenv("TEMP_DIR", "temp")
FRONTEND_DIR = BASE_DIR / "frontend"

# Ensure essential directories exist
for directory in [UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Upload limits
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024

# Defaults
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "en")
DEFAULT_VOICE = os.getenv("DEFAULT_VOICE", "en-US-AriaNeural")
DEFAULT_SPEED = float(os.getenv("DEFAULT_SPEED", "1.0"))

# Voice catalog (Language -> list of supported edge-tts neural voices)
SUPPORTED_VOICES = {
    "en": [
        {
            "id": "en-US-AriaNeural",
            "name": "Aria (US English - Expressive)",
            "gender": "Female",
            "country": "United States",
            "is_default": True
        },
        {
            "id": "en-US-GuyNeural",
            "name": "Guy (US English - Warm & Natural)",
            "gender": "Male",
            "country": "United States",
            "is_default": False
        },
        {
            "id": "en-GB-SoniaNeural",
            "name": "Sonia (UK English - Crisp & Storytelling)",
            "gender": "Female",
            "country": "United Kingdom",
            "is_default": False
        },
        {
            "id": "en-AU-NatashaNeural",
            "name": "Natasha (AU English - Friendly)",
            "gender": "Female",
            "country": "Australia",
            "is_default": False
        }
    ],
    "hi": [
        {
            "id": "hi-IN-SwaraNeural",
            "name": "Swara (Hindi - Natural & Melodic)",
            "gender": "Female",
            "country": "India",
            "is_default": True
        },
        {
            "id": "hi-IN-MadhurNeural",
            "name": "Madhur (Hindi - Clear & Authoritative)",
            "gender": "Male",
            "country": "India",
            "is_default": False
        }
    ],
    "es": [
        {
            "id": "es-ES-ElviraNeural",
            "name": "Elvira (Castilian Spanish - Rich)",
            "gender": "Female",
            "country": "Spain",
            "is_default": True
        },
        {
            "id": "es-MX-DaliaNeural",
            "name": "Dalia (Mexican Spanish - Warm)",
            "gender": "Female",
            "country": "Mexico",
            "is_default": False
        }
    ],
    "fr": [
        {
            "id": "fr-FR-DeniseNeural",
            "name": "Denise (French - Smooth)",
            "gender": "Female",
            "country": "France",
            "is_default": True
        },
        {
            "id": "fr-FR-HenriNeural",
            "name": "Henri (French - Engaging)",
            "gender": "Male",
            "country": "France",
            "is_default": False
        }
    ],
    "de": [
        {
            "id": "de-DE-KatjaNeural",
            "name": "Katja (German - Precise)",
            "gender": "Female",
            "country": "Germany",
            "is_default": True
        },
        {
            "id": "de-DE-ConradNeural",
            "name": "Conrad (German - Resonant)",
            "gender": "Male",
            "country": "Germany",
            "is_default": False
        }
    ]
}

# Maximum character count per TTS audio slice (keeps synthesis snappy and reliable)
TTS_CHUNK_MAX_CHARS = 2500
