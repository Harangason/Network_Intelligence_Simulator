"""Text normalization and extraction helpers for requirement expansion."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from typing import Any


def normalize_text(value: Any) -> str:
    """Normalize free text for rule-based processing."""
    text = str(value or "")
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "ß": "ss",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return " ".join(text.strip().lower().split())


def now_iso() -> str:
    """Return a UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def match_any(text: str, *patterns: str) -> bool:
    """True when one of the regex patterns matches."""
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def extract_int(text: str, patterns: tuple[str, ...] | list[str], default: float | None = None) -> float | None:
    """Extract the first matching integer value from a list of patterns."""
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            value = match.group(1).replace(",", ".")
            try:
                return float(value)
            except ValueError:
                continue
    return default


def extract_first_float(text: str, patterns: tuple[str, ...] | list[str], default: float | None = None) -> float | None:
    """Extract the first matching floating-point number."""
    return extract_int(text, patterns, default=default)


def safe_float(value: object, default: float = 0.0) -> float:
    """Convert mixed values to float with graceful fallback."""
    try:
        if isinstance(value, bool) or value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def round_digits(value: float, digits: int = 3) -> float:
    """Round with deterministic presentation precision."""
    return float(f"{round(float(value), digits):.{digits}f}")


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
