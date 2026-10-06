import asyncio
import os
from pathlib import Path
from typing import Optional, Dict, List, Any
import edge_tts
from gtts import gTTS
from backend.config import SUPPORTED_VOICES, DEFAULT_VOICE, DEFAULT_LANGUAGE

class TTSError(Exception):
    """Exception raised when speech synthesis fails."""
    pass

class TTSService:
    """Handles text-to-speech conversion using edge-tts with gTTS fallback."""

    @staticmethod
    def get_supported_voices() -> Dict[str, List[Dict[str, Any]]]:
        """Return categorized supported voices list."""
        return SUPPORTED_VOICES

    @staticmethod
    def format_rate_string(speed: float) -> str:
        """
        Convert float multiplier (0.75 to 2.0) to edge-tts rate string (+25%, -20%, etc).
        """
        percent = int(round((speed - 1.0) * 100))
        if percent >= 0:
            return f"+{percent}%"
        else:
            return f"{percent}%"

    @classmethod
    async def synthesize_text(
        cls,
        text: str,
        output_file: Path,
        voice: Optional[str] = None,
        language: Optional[str] = None,
        speed: float = 1.0
    ) -> Path:
        """
        Convert text into an MP3 audio file.
        Attempts edge-tts first; falls back to gTTS if edge-tts fails.
        """
        cleaned_text = text.strip()
        if not cleaned_text:
            raise TTSError("Cannot synthesize empty text.")

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        selected_voice = voice or DEFAULT_VOICE
        rate_str = cls.format_rate_string(speed)

        # 1. Attempt edge-tts
        try:
            communicate = edge_tts.Communicate(
                text=cleaned_text,
                voice=selected_voice,
                rate=rate_str
            )
            await communicate.save(str(output_path))

            # Verify generated file exists and is not empty
            if output_path.exists() and output_path.stat().st_size > 100:
                return output_path
        except Exception as edge_err:
            # Log error details and try gTTS fallback
            print(f"[TTSService] edge-tts error: {edge_err}. Attempting gTTS fallback...")

        # 2. Fallback to gTTS if edge-tts failed
        try:
            lang_code = language or "en"
            # Extract simple 2-letter language code if given full code
            if "-" in lang_code:
                lang_code = lang_code.split("-")[0].lower()

            def _run_gtts():
                tts = gTTS(text=cleaned_text, lang=lang_code, slow=(speed < 0.85))
                tts.save(str(output_path))

            # Run synchronous gTTS in threadpool to avoid blocking event loop
            await asyncio.to_thread(_run_gtts)

            if output_path.exists() and output_path.stat().st_size > 100:
                return output_path
            else:
                raise TTSError("gTTS generated an empty audio file.")
        except Exception as gtts_err:
            raise TTSError(f"TTS synthesis failed on both Edge-TTS and gTTS. Error: {str(gtts_err)}")
