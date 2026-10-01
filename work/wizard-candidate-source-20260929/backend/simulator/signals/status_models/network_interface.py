from __future__ import annotations

from typing import Any

from ..states import COMMUNICATION_CODES, communication_at


def network_interface_status(_signal: Any, time_s: float, _context: Any, _state: Any) -> float:
    return float(COMMUNICATION_CODES[communication_at(time_s)])
