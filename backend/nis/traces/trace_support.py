"""Technology-neutral trace timestamps, identifiers and text output."""
from __future__ import annotations
import re
from datetime import datetime, timezone
from pathlib import Path

def utc_now() -> float:
    return datetime.now(timezone.utc).timestamp()


def iso_utc(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def route_label(sender: str, receiver: str) -> str:
    return f"{sender} -> {receiver}"


def safe_identifier(value: str, fallback: str = "NODE") -> str:
    cleaned = re.sub(r"\W+", "_", str(value).strip()).strip("_").upper()
    if not cleaned:
        cleaned = fallback
    if cleaned[0].isdigit():
        cleaned = f"{fallback}_{cleaned}"
    return cleaned


def parse_optional_int(value: object, default: int | None = None) -> int | None:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return int(text, 0)


def triangle_wave(t_s: float, period_s: float, minimum: int, maximum: int) -> int:
    if period_s <= 0:
        return minimum
    phase = (t_s % period_s) / period_s
    y = phase * 2.0 if phase < 0.5 else (1.0 - phase) * 2.0
    return int(minimum + y * (maximum - minimum))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")

def exact_iso_utc(timestamp: float) -> str:
    """Preserve runtime timestamp precision independently of demo exports."""
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat().replace("+00:00", "Z")
