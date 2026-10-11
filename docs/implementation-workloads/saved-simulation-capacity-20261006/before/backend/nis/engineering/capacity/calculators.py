"""Technology-aware, deterministic capacity and timing estimators."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import ceil, isfinite
from typing import Any

from backend.nis.communication.catalog import CAN_FD_DATA_LENGTHS, DIRECT_IO_TECHNOLOGIES, LOCAL_EVIDENCE_FIELDS, REVIEW_RATE_PROPOSALS


from backend.nis.communication.core.timing import FrameEstimate, _positive





def confirmed_serial_evidence(protocol, parameters, payload_bytes=0):
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
    implementation = registry.timing_implementation(protocol)
    handler = getattr(implementation, 'confirmed_serial_evidence', None)
    return handler(protocol, parameters, payload_bytes) if handler else None



def serial_evidence_missing_fields(protocol, parameters, payload_bytes=0):
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
    implementation = registry.timing_implementation(protocol)
    handler = getattr(implementation, 'serial_evidence_missing_fields', None)
    return handler(protocol, parameters, payload_bytes) if handler else []






def estimate_frame(protocol: str, payload_bytes: int, parameters: dict[str, Any]):
    normalized = str(protocol or 'CUSTOM').upper().replace('-', '_').replace(' ', '_')
    payload = max(0, int(payload_bytes))
    if normalized.lower() in DIRECT_IO_TECHNOLOGIES:
        return FrameEstimate(normalized, payload, 0, 0.0, 'DIRECT_IO_NO_FRAME',
                             is_generic_estimate=False, transmission_time_available=False)
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
    implementation = registry.timing_implementation(protocol)
    if implementation is not None and normalized in implementation.FRAME_PROTOCOLS:
        return implementation.estimate_frame(normalized, payload_bytes, parameters)
    frame_bits = (payload + int(_positive(parameters.get('generic_overhead_bytes'), 24))) * 8
    return FrameEstimate(normalized, payload, frame_bits, 0.0, 'GENERIC_ESTIMATE',
                         is_generic_estimate=True, transmission_time_available=False)



def utilization_percent(transmission_time_s: float, cycle_ms: float, multiplicity: int = 1) -> float:
    cycle_s = max(float(cycle_ms), 0.001) / 1000.0
    return max(0.0, transmission_time_s * max(1, multiplicity) / cycle_s * 100.0)





def queueing_delay_ms(transmission_time_s: float, utilization: float) -> float:
    """M/D/1 engineering estimate; bounded near saturation for stable reporting."""
    rho = min(max(utilization / 100.0, 0.0), 0.99)
    return transmission_time_s * 1000.0 * rho / (2.0 * (1.0 - rho))


def scheduled_queueing_delay_ms(
    transmission_time_s: float,
    utilization: float,
    policy: str,
    priority: int = 50,
) -> float:
    """Apply an explicit scheduling assumption to the deterministic queue estimate."""
    base = queueing_delay_ms(transmission_time_s, utilization)
    normalized = str(policy or "FIFO").upper()
    factors = {
        "FIFO": 1.0,
        "PRIORITY": 0.85,
        "STRICT_PRIORITY": 0.7,
        "WEIGHTED_PRIORITY": 0.8,
        "WRR": 0.8,
        "ROUND_ROBIN": 0.95,
        "TIME_TRIGGERED": 0.35,
        "TAS": 0.35,
        "CBS": 0.65,
        "CUSTOM": 1.0,
    }
    if normalized == "FIFO":
        return base
    normalized_priority = max(0, min(priority, 100)) / 100.0
    priority_factor = 1.75 - normalized_priority * 1.25
    return base * factors.get(normalized, 1.0) * priority_factor


def clock_drift_ms(clock_drift_ppm: float, duration_s: float) -> float:
    return max(0.0, float(clock_drift_ppm)) * max(0.0, float(duration_s)) / 1000.0


def classify_load(value: float, thresholds: dict[str, float]) -> str:
    if value >= thresholds["overload"]:
        return "OVERLOAD"
    if value >= thresholds["critical"]:
        return "CRITICAL"
    if value >= thresholds["warning"]:
        return "WARNING"
    return "NORMAL"

from backend.nis.communication.technologies.can_fd.timing import can_fd_wire_data_bytes
from backend.nis.communication.technologies.can.timing import can_frame_time_bound_ms
