import os
import shutil
import struct
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False

class AudioService:
    """Combines and manages audio chunks, chapters, and full audiobooks."""

    @staticmethod
    def is_ffmpeg_available() -> bool:
        """Check whether ffmpeg executable is available on the system path."""
        try:
            res = subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return res.returncode == 0
        except Exception:
            return False

    @classmethod
    def combine_mp3_files(cls, input_files: List[Path], output_file: Path) -> Path:
        """
        Combine multiple MP3 audio files into a single MP3.
        Uses pydub/ffmpeg if available, otherwise uses clean MP3 stream stitching.
        """
        if not input_files:
            raise ValueError("No audio files provided to combine.")

        output_file = Path(output_file)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if len(input_files) == 1:
            shutil.copy2(str(input_files[0]), str(output_file))
            return output_file

        # Try pydub if ffmpeg is available
        if PYDUB_AVAILABLE and cls.is_ffmpeg_available():
            try:
                combined = AudioSegment.empty()
                for f in input_files:
                    seg = AudioSegment.from_file(str(f), format="mp3")
                    combined += seg
                combined.export(str(output_file), format="mp3")
                if output_file.exists() and output_file.stat().st_size > 0:
                    return output_file
            except Exception as e:
                print(f"[AudioService] pydub concatenation failed ({e}). Falling back to MP3 stream joining.")

        # Robust binary MP3 frame joining fallback
        cls._stream_merge_mp3(input_files, output_file)
        return output_file

    @staticmethod
    def _stream_merge_mp3(input_files: List[Path], output_file: Path):
        """
        Merge MP3 files by stripping ID3 metadata tags from secondary chunks
        to produce a seamless, clean audio bitstream.
        """
        with open(output_file, "wb") as out_f:
            for i, in_file in enumerate(input_files):
                if not in_file.exists():
                    continue
                with open(in_file, "rb") as inf:
                    data = inf.read()

                if not data:
                    continue

                if i == 0:
                    # Keep entire first file (including leading ID3v2 header if present)
                    # Strip trailing ID3v1 tag (128 bytes at end starting with 'TAG') if present
                    if len(data) > 128 and data[-128:-125] == b"TAG":
                        data = data[:-128]
                    out_f.write(data)
                else:
                    # Strip ID3v2 header from subsequent files
                    offset = 0
                    if data.startswith(b"ID3") and len(data) >= 10:
                        # ID3v2 size is stored as 4 synchsafe integers at bytes 6..10
                        size_bytes = data[6:10]
                        tag_size = (
                            ((size_bytes[0] & 0x7F) << 21) |
                            ((size_bytes[1] & 0x7F) << 14) |
                            ((size_bytes[2] & 0x7F) << 7) |
                            (size_bytes[3] & 0x7F)
                        )
                        offset = 10 + tag_size

                    # Strip trailing ID3v1 tag
                    end_idx = len(data)
                    if end_idx - offset > 128 and data[-128:-125] == b"TAG":
                        end_idx -= 128

                    chunk_payload = data[offset:end_idx]
                    out_f.write(chunk_payload)

    @classmethod
    def get_mp3_duration(cls, file_path: Path) -> float:
        """
        Accurately estimate or extract duration (in seconds) of an MP3 file.
        """
        if not file_path.exists():
            return 0.0

        # Try pydub if ffmpeg is available
        if PYDUB_AVAILABLE and cls.is_ffmpeg_available():
            try:
                seg = AudioSegment.from_file(str(file_path), format="mp3")
                return len(seg) / 1000.0
            except Exception:
                pass

        # Pure Python MP3 duration calculation from frame headers
        try:
            return cls._calculate_mp3_duration_raw(file_path)
        except Exception:
            # Fallback estimation (edge-tts standard audio is ~48kbps to 64kbps)
            size = file_path.stat().st_size
            return max(1.0, size / 6000.0)

    @staticmethod
    def _calculate_mp3_duration_raw(file_path: Path) -> float:
        """
        Scan MP3 frames to calculate total duration in seconds.
        """
        bitrates = {
            1: [0, 32, 64, 96, 128, 160, 192, 224, 256, 288, 320, 352, 384, 416, 448],  # Layer I
            2: [0, 32, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 384],     # Layer II
            3: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320]      # Layer III
        }
        sample_rates = {
            0: 44100, 1: 48000, 2: 32000
        }

        total_frames = 0
        samples_per_frame = 1152
        sampling_rate = 24000  # Default edge-tts rate

        with open(file_path, "rb") as f:
            data = f.read()

        pos = 0
        length = len(data)

        # Skip ID3v2 if present
        if data.startswith(b"ID3") and length >= 10:
            size_bytes = data[6:10]
            tag_size = (
                ((size_bytes[0] & 0x7F) << 21) |
                ((size_bytes[1] & 0x7F) << 14) |
                ((size_bytes[2] & 0x7F) << 7) |
                (size_bytes[3] & 0x7F)
            )
            pos = 10 + tag_size

        while pos < length - 4:
            # Look for frame sync 11111111 111 (0xFF 0xE0)
            if data[pos] == 0xFF and (data[pos + 1] & 0xE0) == 0xE0:
                header = struct.unpack(">I", data[pos:pos + 4])[0]
                version_bits = (header >> 19) & 0x3
                layer_bits = (header >> 17) & 0x3
                bitrate_idx = (header >> 12) & 0xF
                sample_idx = (header >> 10) & 0x3
                padding = (header >> 9) & 0x1

                layer = 4 - layer_bits if layer_bits else 0
                if layer == 3 and bitrate_idx > 0 and bitrate_idx < 15 and sample_idx < 3:
                    br = bitrates[3][bitrate_idx] * 1000
                    sr = sample_rates[sample_idx]
                    if version_bits == 2:  # MPEG 2.0
                        sr //= 2
                    elif version_bits == 0: # MPEG 2.5
                        sr //= 4
                    sampling_rate = sr
                    frame_len = (144 * br // sr) + padding
                    if frame_len > 0:
                        total_frames += 1
                        pos += frame_len
                        continue
            pos += 1

        if total_frames > 0 and sampling_rate > 0:
            return (total_frames * samples_per_frame) / sampling_rate

        # Simple file-size fallback: edge-tts averages ~6000 bytes per second
        return max(1.0, length / 6000.0)
