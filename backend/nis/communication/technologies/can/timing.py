"""Technology-owned frame and timing implementation; preserved calculation semantics."""
from __future__ import annotations
from math import ceil, isfinite
from typing import Any
from backend.nis.communication.core.timing import FrameEstimate, _positive

from backend.nis.communication.technologies.can_fd.timing import can_fd_wire_data_bytes

def estimate_frame(protocol, payload_bytes, parameters):
    normalized = str(protocol or "CUSTOM").upper().replace("-", "_").replace(" ", "_")
    payload = max(0, int(payload_bytes))
    bitrate = _positive(parameters.get("bitrate"), 0.0)
    rate_confirmed = parameters.get("_rate_evidenced") is not False
    available = bitrate > 0 and rate_confirmed
    if payload > 8 or parameters.get('can_frame_type') == 'REMOTE' and payload:
        raise ValueError('CAN CC payload must be 0..8 B; remote frames have no data field.')
    # Bosch CAN 2.0 Part B 3.2 / 5: stuffing only SOF through CRC sequence.
    # Unknown IDE uses the longer format as a conservative bound, never an inferred 11-bit ID.
    extended = parameters.get('can_frame_format') != 'BASE_11'
    unstuffed = (67 if extended else 47) + payload * 8
    stuffable = (54 if extended else 34) + payload * 8
    frame_bits = unstuffed + (stuffable - 1) // 4
    return FrameEstimate(normalized, payload, frame_bits, frame_bits / bitrate if available else 0.0,
                         "CAN_CC_STUFFING_UPPER_BOUND", calculation_version="2.0", transmission_time_available=available)

def can_frame_time_bound_ms(protocol: str, payload_bytes: int, parameters: dict[str, Any]) -> float | None:
    """Conservative error-free wire-time envelope, not a mean stuffing estimate.

    Reserve 160 non-payload bits and 50% stuffing allowance at the slower phase
    rate. This intentionally overbounds standard/FD overhead, CRC, intermission,
    fixed/dynamic stuffing and FD DLC padding. No retry budget is implied.
    """
    normalized = str(protocol).upper().replace("-", "_")
    if normalized not in {"CAN", "CAN_CLASSIC", "CAN_FD", "CANFD"}:
        return None
    payload = max(0, int(payload_bytes))
    if normalized in {"CAN_FD", "CANFD"}:
        payload = can_fd_wire_data_bytes(payload,parameters)
    if parameters.get("_rate_evidenced") is False:
        return None
    bitrate = _positive(parameters.get("arbitration_bitrate", parameters.get("bitrate")), 0)
    if normalized in {"CAN_FD", "CANFD"} and parameters.get('can_fd_brs') is not False:
        bitrate = min(bitrate, _positive(parameters.get("data_bitrate"), 0))
    if not bitrate:
        return None
    return ceil((160 + 8 * payload) * 1.5) / bitrate * 1000

def prepare_timing_parameters(payload_bytes, bitrate=None, *, arbitration_bitrate=None, data_bitrate=None, local_timing_evidence=None, can_fd_brs=None, can_frame_format=None, can_fd_dlc=None, can_fd_wire_data_bytes=None):
    technology_id = 'can'
    if not bitrate:
        raise ValueError(f"{technology_id} benötigt eine bestätigte Bitrate.")
    rate_parameters = {"bitrate_bps": bitrate}
    frame_parameters = {"bitrate": bitrate}
    native = {key:value for key,value in {'can_fd_brs':can_fd_brs,'can_frame_format':can_frame_format,
                'can_fd_dlc':can_fd_dlc,'can_fd_wire_data_bytes':can_fd_wire_data_bytes}.items() if value is not None}
    if set(native) - {'can_frame_format'}:
        raise ValueError('CAN timing options are not applicable to this technology.')
    rate_parameters.update(native)
    frame_parameters.update(native)
    return rate_parameters, frame_parameters

def validate_timing_scope(payload_bytes, bitrate, rate_parameters, frame_parameters):
    return None

FRAME_PROTOCOLS = ('CAN', 'CAN_CLASSIC')

from .definition import PROFILE
SCHEDULE_PAYLOAD_LIMIT = PROFILE["max_payload_bytes"]
