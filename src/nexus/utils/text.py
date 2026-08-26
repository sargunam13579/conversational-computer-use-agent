"""
NEXUS Text Processing Utilities.

Common text operations: normalization, truncation, formatting.
"""

from __future__ import annotations

import re
import unicodedata


def normalize_text(text: str) -> str:
    """
    Normalize user input text for consistent processing.

    - Strips leading/trailing whitespace
    - Collapses multiple spaces
    - Normalizes unicode characters
    """
    text = text.strip()
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text)
    return text


def truncate(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """Truncate text to a maximum length, adding a suffix if truncated."""
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix


def extract_code_blocks(text: str) -> list[dict[str, str]]:
    """
    Extract fenced code blocks from markdown-formatted text.

    Returns a list of dicts with 'language' and 'code' keys.
    """
    pattern = r"```(\w*)\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    return [{"language": lang or "text", "code": code.strip()} for lang, code in matches]


def format_file_size(size_bytes: int) -> str:
    """Format a byte count as a human-readable file size."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024  # type: ignore[assignment]
    return f"{size_bytes:.1f} PB"


def sanitize_filename(name: str) -> str:
    """Remove or replace characters that are invalid in filenames."""
    # Remove characters invalid on Windows
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", name)
    sanitized = sanitized.strip(". ")
    return sanitized or "unnamed"
