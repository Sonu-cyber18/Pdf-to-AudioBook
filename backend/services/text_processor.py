import re
from typing import List, Dict, Any, Tuple
from collections import Counter
from backend.config import TTS_CHUNK_MAX_CHARS

# Common chapter regex patterns
CHAPTER_PATTERNS = [
    # Chapter 1, Chapter One, CHAPTER IV, Chapter 1: The Beginning
    re.compile(r"^\s*(chapter|ch\.|kapitel|chapitre)\s+([0-9ivxlcdm]+|[a-z]+)(\s*[:\-\u2013\u2014]\s*(.+))?$", re.IGNORECASE),
    # 1. Introduction, 2. Getting Started
    re.compile(r"^\s*([0-9]+)\.\s+([A-Z][A-Za-z0-9\s,'\"\-]{2,50})$"),
    # SECTION I, PART 1, BOOK TWO
    re.compile(r"^\s*(section|part|book|act)\s+([0-9ivxlcdm]+|[a-z]+)(\s*[:\-\u2013\u2014]\s*(.+))?$", re.IGNORECASE),
    # Standalone standard headings: Prologue, Epilogue, Introduction, Conclusion, Preface, Foreword, Afterword
    re.compile(r"^\s*(prologue|epilogue|introduction|conclusion|preface|foreword|afterword|appendix)\b(\s*[:\-\u2013\u2014]\s*(.+))?$", re.IGNORECASE)
]

# Standalone page number patterns
PAGE_NUMBER_PATTERNS = [
    re.compile(r"^\s*\d+\s*$"),                                      # " 12 "
    re.compile(r"^\s*[-–—]\s*\d+\s*[-–—]\s*$"),                     # "- 12 -"
    re.compile(r"^\s*page\s+\d+(\s+of\s+\d+)?\s*$", re.IGNORECASE),  # "Page 12 of 100"
    re.compile(r"^\s*\[\s*\d+\s*\]\s*$")                            # "[12]"
]

class ChapterInfo:
    def __init__(self, title: str, start_page: int, text: str = ""):
        self.title = title
        self.start_page = start_page
        self.text = text
        self.chunks: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "start_page": self.start_page,
            "char_count": len(self.text),
            "word_count": len(self.text.split()),
            "chunks_count": len(self.chunks)
        }

class TextProcessor:
    """Handles text cleanup, header/footer stripping, chapter detection, and chunking."""

    def __init__(self, max_chunk_chars: int = TTS_CHUNK_MAX_CHARS):
        self.max_chunk_chars = max_chunk_chars

    def clean_page_text(self, text: str) -> str:
        """
        Normalize Unicode, whitespace, and punctuation for natural TTS reading.
        """
        if not text:
            return ""

        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Normalize smart punctuation to clean ASCII / TTS friendly pauses
        replacements = {
            "\u201c": '"', "\u201d": '"',    # Double quotes
            "\u2018": "'", "\u2019": "'",    # Single quotes
            "\u2014": " — ", "\u2013": " — ", # Em and En dashes
            "\u2026": "...",                 # Ellipsis
            "\u00a0": " ",                   # Non-breaking space
            "\t": " ",
            "\u2022": ", ",                  # Bullet
            "•": ", "
        }
        for orig, rep in replacements.items():
            text = text.replace(orig, rep)

        # Remove form feed / weird control characters (keep \n and normal punctuation)
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

        # Remove repeated hyphens or underscores
        text = re.sub(r"_{3,}", " ", text)
        text = re.sub(r"-{3,}", " - ", text)

        return text

    def detect_and_remove_headers_footers(self, raw_pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identify repeated headers and footers that appear across multiple pages.
        """
        if len(raw_pages) <= 2:
            # Not enough pages to accurately determine recurring headers
            return raw_pages

        top_lines: List[str] = []
        bottom_lines: List[str] = []

        for p in raw_pages:
            lines = [line.strip() for line in p["text"].split("\n") if line.strip()]
            if lines:
                top_lines.append(lines[0])
                if len(lines) > 1:
                    bottom_lines.append(lines[-1])

        # Find repeated candidates appearing in >= 30% of pages
        threshold = max(3, int(len(raw_pages) * 0.25))
        repeated_headers = {
            line for line, count in Counter(top_lines).items()
            if count >= threshold and not self._is_potential_chapter_title(line)
        }
        repeated_footers = {
            line for line, count in Counter(bottom_lines).items()
            if count >= threshold and not self._is_potential_chapter_title(line)
        }

        cleaned_pages = []
        for p in raw_pages:
            raw_lines = [self.clean_page_text(l) for l in p["text"].split("\n")]
            filtered_lines = []

            for line in raw_lines:
                stripped = line.strip()
                if not stripped:
                    filtered_lines.append("")
                    continue

                # Check if it matches page numbers
                if any(pat.match(stripped) for pat in PAGE_NUMBER_PATTERNS):
                    continue

                # Check if it is a repeated header/footer
                if stripped in repeated_headers or stripped in repeated_footers:
                    continue

                filtered_lines.append(line)

            # Recombine and collapse excessive blank lines
            cleaned_text = "\n".join(filtered_lines)
            cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text).strip()

            cleaned_pages.append({
                "page_number": p["page_number"],
                "text": cleaned_text
            })

        return cleaned_pages

    def _is_potential_chapter_title(self, line: str) -> bool:
        """Check if line matches any chapter regex pattern."""
        line_clean = line.strip()
        if len(line_clean) > 80:
            return False
        for pat in CHAPTER_PATTERNS:
            if pat.match(line_clean):
                return True
        return False

    def detect_chapters(self, cleaned_pages: List[Dict[str, Any]]) -> List[ChapterInfo]:
        """
        Detect chapters across document pages.
        Falls back to logical sections if no chapters or only 1 chapter is detected.
        """
        detected_chapters: List[ChapterInfo] = []
        current_chapter: Optional[ChapterInfo] = None
        current_text_blocks: List[str] = []

        for page in cleaned_pages:
            p_num = page["page_number"]
            lines = page["text"].split("\n")

            for line in lines:
                stripped = line.strip()
                if self._is_potential_chapter_title(stripped):
                    # Finalize current chapter if text exists
                    if current_chapter and current_text_blocks:
                        current_chapter.text = "\n\n".join(current_text_blocks).strip()
                        detected_chapters.append(current_chapter)
                        current_text_blocks = []

                    title = stripped
                    current_chapter = ChapterInfo(title=title, start_page=p_num)
                else:
                    if stripped:
                        current_text_blocks.append(stripped)

        # Append last chapter
        if current_chapter:
            current_chapter.text = "\n\n".join(current_text_blocks).strip()
            detected_chapters.append(current_chapter)
        elif current_text_blocks:
            # No chapter headings found at all
            full_text = "\n\n".join(current_text_blocks).strip()
            return self._split_into_logical_sections(cleaned_pages, full_text)

        # Filter out accidental tiny detections (< 50 characters)
        meaningful_chapters = [ch for ch in detected_chapters if len(ch.text) >= 50]

        # If chapter detection found less than 2 distinct chapters, divide into logical sections
        if len(meaningful_chapters) < 2:
            full_text = "\n\n".join(p["text"] for p in cleaned_pages if p["text"]).strip()
            return self._split_into_logical_sections(cleaned_pages, full_text)

        # Chunk each chapter
        for ch in meaningful_chapters:
            ch.chunks = self.split_into_tts_chunks(ch.text)

        return meaningful_chapters

    def _split_into_logical_sections(self, cleaned_pages: List[Dict[str, Any]], full_text: str) -> List[ChapterInfo]:
        """
        Fallback when automatic chapter headings aren't detected.
        Divides book into sensible sections of ~15-20 pages or ~3000 words.
        """
        if not full_text:
            return []

        # Divide based on pages count
        pages_count = len(cleaned_pages)
        if pages_count <= 10:
            # Single unified section
            ch = ChapterInfo(title="Complete Document", start_page=1, text=full_text)
            ch.chunks = self.split_into_tts_chunks(full_text)
            return [ch]

        # Divide every 10-15 pages
        chunk_page_size = 10 if pages_count <= 30 else 15
        sections: List[ChapterInfo] = []
        cur_pages: List[str] = []
        start_p = 1
        sec_num = 1

        for i, p in enumerate(cleaned_pages):
            if p["text"]:
                cur_pages.append(p["text"])
            if (i + 1) % chunk_page_size == 0 or (i + 1) == pages_count:
                sec_text = "\n\n".join(cur_pages).strip()
                if sec_text:
                    end_p = p["page_number"]
                    title = f"Section {sec_num} (Pages {start_p}-{end_p})" if start_p != end_p else f"Section {sec_num} (Page {start_p})"
                    sec = ChapterInfo(title=title, start_page=start_p, text=sec_text)
                    sec.chunks = self.split_into_tts_chunks(sec_text)
                    sections.append(sec)
                    sec_num += 1
                cur_pages = []
                start_p = p["page_number"] + 1

        return sections if sections else [ChapterInfo(title="Audiobook", start_page=1, text=full_text)]

    def split_into_tts_chunks(self, text: str) -> List[str]:
        """
        Split long text into manageable chunks without breaking sentences in the middle.
        Maximum length per chunk is bounded by self.max_chunk_chars.
        """
        if not text:
            return []

        # Split on paragraph boundaries first
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks: List[str] = []
        current_chunk = []
        current_length = 0

        for para in paragraphs:
            para_len = len(para)

            # If the paragraph alone fits in the current chunk
            if current_length + para_len + 2 <= self.max_chunk_chars:
                current_chunk.append(para)
                current_length += para_len + 2
            else:
                # Flush existing chunk if non-empty
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_length = 0

                # If paragraph itself is larger than max_chunk_chars, split by sentence
                if para_len > self.max_chunk_chars:
                    sentence_chunks = self._split_paragraph_by_sentences(para)
                    for sc in sentence_chunks:
                        if current_length + len(sc) + 2 <= self.max_chunk_chars:
                            current_chunk.append(sc)
                            current_length += len(sc) + 2
                        else:
                            if current_chunk:
                                chunks.append("\n\n".join(current_chunk))
                                current_chunk = []
                                current_length = 0
                            current_chunk.append(sc)
                            current_length = len(sc)
                else:
                    current_chunk.append(para)
                    current_length = para_len

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return [c.strip() for c in chunks if c.strip()]

    def _split_paragraph_by_sentences(self, paragraph: str) -> List[str]:
        """Split a long paragraph into sentence-bounded slices."""
        # Regex splits on sentence endings followed by space or newline
        raw_sentences = re.split(r'(?<=[.!?])\s+', paragraph)
        sentences = [s.strip() for s in raw_sentences if s.strip()]

        slices: List[str] = []
        current_slice = []
        current_len = 0

        for sentence in sentences:
            s_len = len(sentence)
            if s_len > self.max_chunk_chars:
                # Sentence is unusually long (run-on sentence). Split by commas or word boundaries.
                words = sentence.split(" ")
                sub_slice = []
                sub_len = 0
                for w in words:
                    if sub_len + len(w) + 1 <= self.max_chunk_chars:
                        sub_slice.append(w)
                        sub_len += len(w) + 1
                    else:
                        if sub_slice:
                            slices.append(" ".join(sub_slice))
                        sub_slice = [w]
                        sub_len = len(w)
                if sub_slice:
                    slices.append(" ".join(sub_slice))
            elif current_len + s_len + 1 <= self.max_chunk_chars:
                current_slice.append(sentence)
                current_len += s_len + 1
            else:
                if current_slice:
                    slices.append(" ".join(current_slice))
                current_slice = [sentence]
                current_len = s_len

        if current_slice:
            slices.append(" ".join(current_slice))

        return slices
